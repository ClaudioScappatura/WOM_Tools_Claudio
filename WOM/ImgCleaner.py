import copy
import os
import shutil
import subprocess
import re
from collections import Counter
from tkinter import filedialog
import natsort
import numpy as np
import photoshop.api as ps
import wmi
from photoshop.api import Application
import cv2
from paddleocr import PaddleOCR
import TypesetPsd

PS_VERSION = None
# TODO Inserire assieme al nome del watermark, dei parametri x1,y1,x2,y2 da utilizzare per adattare la selezione di pulizia del WM
watermark = ["lunarscan"]


# Verifica la presenza della GPU
def check_nvidia_gpu():
    c = wmi.WMI()
    for gpu in c.Win32_VideoController():
        if "nvidia" in gpu.Name.lower():
            print("La scheda grafica è una NVIDIA.")
            return True
        else:
            print("La scheda grafica non è una NVIDIA o non è stata trovata.")
    return False


# Verifica la versione di photoshop
def get_ps_version():
    command = r'Get-ItemProperty HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | ' \
              r'Select-Object DisplayName, DisplayVersion | Format-Table –AutoSize | ' \
              r'findstr Photoshop'

    # 'Get-ItemProperty HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | Select-Object DisplayName, DisplayVersion | Format-Table –AutoSize | findstr Photoshop'
    try:
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True)

        if result.returncode == 0:
            result = result.stdout.strip()
            if len(result) > 0:
                pattern = r"\d+\.\d+\.\d+\.\d+"  # Pattern per trovare le parti numeriche
                matches = re.findall(pattern, result)
                if matches:
                    # Prendi la prima versione trovata
                    versione_recente = matches[0]
                    print("Versione:", versione_recente)
                    return versione_recente
                else:
                    print("Nessuna versione trovata.")
                    return None
            else:
                return None
        else:
            print("Errore durante l'esecuzione del comando PowerShell")
            return None
    except Exception as e:
        print("Errore durante la ricerca di Photoshop", str(e))
        return None


# Crea il path indicato se non esiste
def check_path_existence(path_to_check: str):
    if not os.path.exists(path_to_check):
        os.makedirs(path_to_check)


# Salvataggio dell'immagine con PS
def ps_save_image(initial_image: str, exit_psd=False, position_save: str = None):
    try:
        app = Application()
        doc = app.open(initial_image)
        file_name, file_extension = os.path.splitext(os.path.basename(initial_image))
        if position_save:
            initial_image = os.path.dirname(initial_image) + position_save
            check_path_existence(initial_image)
            initial_image += (file_name + file_extension)
        if file_extension.lower() in [".jpg", ".jpeg"]:
            doc.saveAs(initial_image, ps.JPEGSaveOptions(quality=10))
        elif file_extension.lower() == ".png":
            doc.saveAs(initial_image, ps.PNGSaveOptions(compression=2))
        if exit_psd:
            try:
                doc.close()
            except Exception as e:
                print(f"Errore durante la chiusura del documento PSD: {e}")
    except Exception as e:
        print(f"Errore durante il salvataggio dell'immagine: {e}")


# Azioni richieste a Photoshop
def ps_actions(ps_image: str, action_name: str, layer_name: str = "Auto-Clean", doc: Application.activeDocument = None,
               x_sx: float | int = 0, y_up: float | int = 0, x_dx: float | int = 0, y_down: float | int = 0):
    try:
        app = Application()
        if doc is None:
            doc = app.open(ps_image)

        if action_name.lower() == "start":
            # Conversione in RGB per poter usare il GenerativeFill
            app.DoAction('beRGB', 'AutoCleaner')
            auto_clean = doc.activeLayer
            auto_clean.name = "Auto-Clean"

        elif action_name.lower() == "selection":
            sel_coord = ((int(x_sx), int(y_up)),
                         (int(x_dx), int(y_up)),
                         (int(x_dx), int(y_down)),
                         (int(x_sx), int(y_down)))
            doc.selection.select(sel_coord, ps.SelectionType.ExtendSelection)
        # Riempimento di bianco
        elif action_name.lower() == "white_fill":
            app.doAction('LevelOne', 'AutoCleaner')
            doc.selection.expand(7)
            app.DoAction('WhiteFill', 'AutoCleaner')
            doc.selection.deselect()
        # Riempimento con Generative-Fill
        elif action_name.lower() == "generative_fill":
            app.doAction('LevelOne', 'AutoCleaner')
            doc.selection.expand(11)
            app.DoAction('AzioneFill', 'AutoCleaner')
            doc.selection.deselect()
        elif action_name.lower() == "only_visible":
            layer_found = False
            for layer in doc.layers:
                if layer.name != layer_name:
                    if layer_found:
                        layer.visible = False
                else:
                    layer_found = True
            app.doAction('LevelOne', 'AutoCleaner')
        elif action_name.lower() == "all_visible":
            for layer in doc.layers:
                layer.visible = True

    except Exception as e:
        print(f"Errore durante l'esecuzione dell'azione: {e}")


def get_center(box):
    """Calcola il centro di un box."""
    x1, y1, x2, y2 = box[:4]
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2])


def get_size(box):
    """Calcola la dimensione di un box."""
    x1, y1, x2, y2 = box[:4]
    return np.linalg.norm(np.array([x2 - x1, y2 - y1]))


# Merge dei box da pulire con il generative fill
def merge_boxes(boxes, threshold_ratio):
    # Unisce i box che sono più vicini di una certa soglia.
    # Calcola la dimensione media dei box
    average_size = np.mean([get_size(box) for box in boxes])
    # Imposta la soglia come una frazione della dimensione media
    threshold = threshold_ratio * average_size

    merged_boxes = boxes
    while True:
        new_boxes = []
        for box in merged_boxes:
            if not new_boxes:
                new_boxes.append(box)
                continue
            center = get_center(box)
            for i, new_box in enumerate(new_boxes):
                new_center = get_center(new_box)
                if np.linalg.norm(center - new_center) < threshold:
                    # Unisci i box prendendo il minimo x1, y1 e il massimo x2, y2
                    x1, y1, x2, y2, text = box
                    nx1, ny1, nx2, ny2, new_text = new_box
                    new_boxes[i] = [min(x1, nx1), min(y1, ny1), max(x2, nx2), max(y2, ny2), new_text + " " + text]
                    break
            else:
                new_boxes.append(box)
        if len(new_boxes) == len(merged_boxes):
            # Se non ci sono più box da unire, esci dal ciclo
            break
        merged_boxes = new_boxes
    return merged_boxes


# Verifica se è passata una cartella ed estrapola i riferimenti alle immagini
def get_images_list(element: str | list):
    if isinstance(element, str):
        # cartella
        if os.path.isdir(element):
            estensioni_immagini = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
            elenco_immagini = [os.path.join(element, file) for file in natsort.natsorted(os.listdir(element))
                               if os.path.isfile(os.path.join(element, file)) and
                               os.path.splitext(file)[1].lower() in estensioni_immagini]
            return elenco_immagini, True
        else:
            # singola immagine
            return element, False
    else:
        # lista d'immagini
        return element, False


# ----------------------------- PULIZIA DEL TESTO SU SFONDO UNIFORME -----------------------------

# Espande il box
def expand_box(box, expand, image):
    height, width = image.shape[:2]
    x1 = max(box[0] - expand, 0)
    y1 = max(box[1] - expand, 0)
    x2 = min(box[2] + expand, width - 1)
    y2 = min(box[3] + expand, height - 1)
    return [x1, y1, x2, y2]


def get_color(image, x, y):
    # Ottieni il colore del pixel alle coordinate (x, y) dall'immagine
    b, g, r = image[y, x]  # OpenCV rappresenta i canali di colore in ordine BGR
    # Restituisci il colore come una tupla di valori (B, G, R)
    return int(b), int(g), int(r)


# Recupera il colore dei pixel attorno al box
def get_pixel_colors_list(x1, x2, y1, y2, image):
    colors = []
    # Aggiungi i colori dei quattro lati del perimetro alla lista dei colori
    for x in range(x1, x2 + 1):
        colors.append(get_color(image, x, y1))  # Lato superiore
        colors.append(get_color(image, x, y2))  # Lato inferiore
    for y in range(y1 + 1, y2):  # Evita di considerare i vertici già contati
        colors.append(get_color(image, x1, y))  # Lato sinistro
        colors.append(get_color(image, x2, y))  # Lato destro

    return colors


# Analizza il colore dei pixel attorno al box
def get_perimeter_colors(box, image, expand, tolerance: float = 0.85, show_percentage: bool = False):
    x1, y1, x2, y2 = expand_box(box, expand + 2, image)
    # Conta i colori nel perimetro
    color_counts_with_expand = Counter(get_pixel_colors_list(x1, x2, y1, y2, image))
    x1, y1, x2, y2 = expand_box(box, expand, image)
    color_counts = Counter(get_pixel_colors_list(x1, x2, y1, y2, image))
    if color_counts.most_common(1)[0][0] == color_counts_with_expand.most_common(1)[0][0]:
        total_pixels = 2 * (x2 - x1 + y2 - y1)

        # Trova il colore dominante nel perimetro
        dominant_color, dominant_count = color_counts.most_common(1)[0]
        total_count = dominant_count
        allowed_differences = [0, 1, 2, 3]
        # Aggiunge alle occorrenze del colore dominante, le occorrenze dei colori che si discostano da 1 a 3 punti colore
        for index, (color, count) in enumerate(color_counts.most_common()):
            if index == 0:  # Evito che conti di nuovo le occorrenze del colore dominante
                continue

            if all(abs(color[channel] - dominant_color[channel]) in allowed_differences for channel in range(3)):
                total_count += count

        # Calcola la percentuale di pixel con il colore dominante
        dominant_percentage = round(total_count / total_pixels, 2)
        if show_percentage:
            return dominant_percentage, dominant_color

        # Verifica se il colore dominante supera la soglia di tolleranza
        if dominant_percentage >= tolerance:
            return dominant_color
        else:

            return None
    else:
        return None


# In base al colore dei pixel analizzati, decide se riempire con il bianco o con il generative fill
def analyze_and_remove(path_image: str, result_ocr: list[
    list[tuple[str, None]]], psd_image: bool, mask_img: bool, png_image: bool, destination_path: str | None = None,
                       clear_all: bool = False, onomatopee: list | str = ""):
    if destination_path is None:
        # TODO Utilizzare il join per evitare problemi dovuti all'inserimento manuale del path di salvataggio
        destination_path = path_image
    else:
        destination_path += ("/" + os.path.basename(path_image))
    try:
        img_binary = cv2.imread(path_image)
        img_height, img_width = img_binary.shape[:2]
        mask_binary = np.ones((img_height, img_width, 4), dtype=np.uint8)

        not_cleaned = []  # Parole da togliere con il Generative Fill
        for coord in result_ocr:
            tolerance = 0.85
            for repetition in range(10):
                for box in coord:
                    # TODO Capire come utilizzare Numpy
                    try:
                        x1, y1, x2, y2 = int(box[0][0][0]), int(box[0][0][1]), int(box[0][2][0]), int(box[0][2][1])
                        # TODO Studiare un metodo automatico per il riconoscere la grandezza del watermark
                        if any(item in box[1][0].lower() for item in watermark):
                            # Modifica delle coordinate per selezionare l'intero watermark
                            # Attualmente queste coordinate sono specifiche per "lunarscan" in sextudy
                            x1 -= 50
                            y1 -= 6
                            x2 += 10
                            y2 += 6

                        # Date le coordinate del box di contenimento della parola, espande il box un pixel alla volta (max.8)
                        # I box sono possono esser più piccoli della parola (perché ES: hanno dei bordi aggiuntivi) e per questo espandiamo
                        for exp in range(0, 8, 1):
                            # Controlla il colore di ogni pixel che circonda il box
                            # Se rileva una dominante netta, restituisce il colore
                            result_color = get_perimeter_colors(box=[x1, y1, x2, y2], image=img_binary, expand=exp,
                                                                tolerance=tolerance)
                            # Box circondato dallo stesso colore
                            if result_color is not None:
                                # Applico modifiche su copia dell'immagine
                                # Se si vuole il png ma non si userà ps
                                max_percent = [exp,
                                               get_perimeter_colors(box=[x1, y1, x2, y2], image=img_binary, expand=exp,
                                                                    show_percentage=True)[0]]
                                for line in range(exp + 1, exp + 6, 1):
                                    temp_perc = get_perimeter_colors(box=[x1, y1, x2, y2], image=img_binary,
                                                                     expand=line, show_percentage=True)
                                    if result_color == temp_perc[1]:
                                        if temp_perc[0] > max_percent[1]:
                                            max_percent = [line, temp_perc[0]]
                                            if temp_perc[0] >= 0.98:
                                                break
                                img_binary = cv2.rectangle(img_binary,
                                                           (int(x1) - max_percent[0], int(y1) - max_percent[0]),
                                                           (int(x2) + max_percent[0], int(y2) + max_percent[0]),
                                                           (result_color[0], result_color[1], result_color[2]), -1)
                                # Applico modifiche su un png trasparente
                                if psd_image or mask_img or clear_all:
                                    mask_binary = cv2.rectangle(mask_binary,
                                                                (int(x1) - max_percent[0], int(y1) - max_percent[0]),
                                                                (int(x2) + max_percent[0], int(y2) + max_percent[0]), (
                                                                    result_color[0] - 1, result_color[1] - 1,
                                                                    result_color[2] - 1, 255), -1)
                                print(f"Testo pulito: {box[1][0]} -- affidabilità: {box[1][1]}")
                                coord.remove(box)  # Rimozione parola pulita
                                break
                        # All'ultima iterazione i box non ancora puliti vengono inseriti in una lista
                        if repetition == 9 and clear_all:
                            not_cleaned.append([x1, y1, x2, y2, box[1][0]])
                            print(f"DA PULIRE con PS: {box[1][0]}")

                    except Exception as e:
                        print(f"Errore durante l'elaborazione del box: {e}")
                try:
                    if repetition == 9:
                        # Se non bisogna utilizzare il generative fill, si salvano le immagini senza aprire PS
                        if not clear_all:
                            if png_image:
                                save_img_balloon_cleaned(destination_path, "/clean_png/", img_binary)
                            if mask_img:
                                save_img_balloon_cleaned(destination_path, "/clean_mask/", mask_binary)
                            if psd_image:
                                # Salvataggio temporaneo della maschera per creare il psd successivamente
                                save_img_balloon_cleaned(path_image, "/temp_clean/", mask_binary)
                        else:
                            # C'è bisogno di PS quindi i file verranno salvati dopo il generative fill
                            save_img_balloon_cleaned(path_image, "/temp_clean/", mask_binary)
                except Exception as e:
                    print(f"Errore durante il salvataggio dell'immagine con i balloon puliti: {e}")

            # Se si vuole pulire l'intera immagine
            if clear_all:
                # Se c'è ancora almeno una parola da togliere con PS
                if len(not_cleaned) > 0:
                    try:
                        parent_path = os.path.dirname(path_image)
                        file_name = os.path.basename(path_image)
                        # Merge dei box di testo adiacenti (facilita il generative fill di PS)
                        merge_remaining_boxes = merge_boxes(not_cleaned, 1)
                        file_to_open = parent_path + "/temp_clean/" + file_name
                        # Crea un psd con RAW e maschera con i balloon puliti. In questa maniera è possibile applicare il GF (impossibile applicarlo solo sulla maschera)
                        doc = assemble_psd(cleaned_img=file_to_open, raw_img=path_image)
                        for coords in merge_remaining_boxes:
                            # Esclude i testo di max 3 lettere (utile per evitare la pulizia di simboli erroneamente riconosciuti come testo)
                            if len(coords[4]) > 4:
                                # Effettua la selezione su PS del box
                                ps_actions(ps_image=path_image, action_name="selection", x_sx=coords[0], y_up=coords[1],
                                           x_dx=coords[2], y_down=coords[3])
                                # Applica il GF sulla selezione
                                ps_actions(action_name="generative_fill", ps_image=path_image)
                        try:
                            if png_image:
                                # Salva il png con tutte le correzioni
                                ps_save_image(path_image, position_save="/clean_png/", exit_psd=False)
                            if mask_img:
                                # Rende visibile solamente i livelli con le correzioni e salva
                                ps_actions(path_image, 'only_visible')
                                ps_save_image(path_image, position_save="/clean_mask/", exit_psd=False)
                                ps_actions(path_image, 'all_visible')
                        except Exception as e:
                            print(f"Errore durante il salvataggio post generative-fill: {e}")

                        return doc

                    except Exception as e:
                        print(f"Errore durante il merge dei box di testo oppure generative fill: {e}")
                else:
                    # Non è stato utilizzato il generative fill
                    return None
    except Exception as e:
        print(f"Errore durante l'analisi e rimozione delle parole: {e}")
        return None


# Salva le immagini CV2
def save_img_balloon_cleaned(img_path: str, dest_folder: str, cv2_img):
    parent_path = os.path.dirname(img_path)
    check_path_existence(parent_path + "/" + dest_folder)

    file_name, file_extension = os.path.splitext(os.path.basename(img_path))
    # Salva l'immagine
    cv2.imwrite(parent_path + dest_folder + file_name + ".png", cv2_img)
    print("Salvata:", parent_path + dest_folder + file_name + ".png")


# Funzione che inserisce in un nuovo PSD l'immagine RAW e quella pulita automaticamente
def assemble_psd(cleaned_img: str, raw_img: str = None):
    try:
        app = Application()
        doc2 = app.open(cleaned_img)
        doc2.activeLayer.name = "AutoClean"
        doc2.selection.copy()

        doc1 = app.open(raw_img)
        # Imposta il metodo colore su RBG (il GF funziona solo così)
        app.DoAction('beRGB', 'AutoCleaner')
        doc1.activeLayer.name = "RAW"
        doc1.paste()
        auto_clean = doc1.activeLayer
        auto_clean.name = "Auto-Clean"
        doc2.close()
        return doc1
    except Exception as e:
        print(f"Errore durante l'assemblaggio dei PSD: {e}")


# rimuove le cartelle create per via dello slicer
def remove_other_dir(parent_dir_path: str):
    if os.path.exists(parent_dir_path + "/temp_clean"):
        shutil.rmtree(parent_dir_path + "/temp_clean")


# Per debuggare, mostra l'immagine
def show_image(image, scale_percent):
    # Calcola le nuove dimensioni dell'immagine
    width = int(image.shape[1] * scale_percent / 100)
    height = int(image.shape[0] * scale_percent / 100)
    dim = (width, height)

    # Ridimensiona l'immagine
    img_resized = cv2.resize(image, dim, interpolation=cv2.INTER_AREA)

    # Visualizza l'immagine
    cv2.imshow('Image with boxes', img_resized)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# Analizza l'input (cartella o file), riconosce il testo, type del testo
def start_detect_processing(gpu: bool = False, clear_all: bool = False, save_and_exit: bool = False,
                            img_path: str | list = None, psd_type=True,
                            destination_path: str | None = None, psd_image: bool = False, mask_img: bool = True,
                            png_image: bool = True):
    try:
        ocr = PaddleOCR(use_angle_cls=False, lang='en', ocr_order_method="det_ar", use_gpu=gpu,
                        det_db_score_mode="slow", max_text_length=200, cpu_math_library_num_threads=4, use_mp=True,
                        det_db_thresh=0.3, det_limit_side_len=17000, det_db_unclip_ratio=1.5, det_db_box_thresh=0.3,
                        e2e_pgnet_mode='accurate', cls_thresh=0.2, drop_score=0.2, e2e_limit_side_len=17000)

        img_path_list_to_clean, is_dir = get_images_list(img_path)
        img_path = os.path.dirname(img_path_list_to_clean[0])

        pred_list = []
        threads = []

        # TODO Implementare il multithread per l'ocr
        for img in img_path_list_to_clean:
            pred_groups = ocr.ocr(img, cls=False)
            if psd_type:
                # Fa una copia integrale della lista poiché 'pred_groups' cambia nel tempo
                pred_list = copy.deepcopy(pred_groups)

            doc = analyze_and_remove(path_image=img, result_ocr=pred_groups, clear_all=clear_all, psd_image=psd_image,
                                     mask_img=mask_img, png_image=png_image, destination_path=destination_path)

            if psd_image:
                # Se non è stato utilizzato il GF e quindi non il psd va ancora assemblato
                if doc is None:
                    doc = assemble_psd(cleaned_img=img_path + "/temp_clean/" + os.path.basename(img), raw_img=img)
                # salvataggio del psd in posizione da input
                if destination_path is None:
                    destination_path = img_path
                output_folder = destination_path + "/PSD_Cleaned"
                check_path_existence(output_folder)

                output_path = os.path.join(output_folder, os.path.basename(img))
                doc.saveAs(output_path, ps.PhotoshopSaveOptions(), asCopy=False)
                # Inserisce i livelli di testo nel psd
                if psd_type:
                    TypesetPsd.type_boxes(doc, pred_list, watermark)
                    doc.saveAs(output_path, ps.PhotoshopSaveOptions(), asCopy=False)
                # chiude il psd
                if save_and_exit:
                    doc.close()
        # Rimozione cartella di appoggio 'temp_clean'
        remove_other_dir(img_path)
    except Exception as e:
        print(f"Errore durante l'avvio del processo di rilevamento e elaborazione: {e}")


def start():
    # Immagini
    image_paths = filedialog.askopenfilenames(
        title="Scegli la prima immagine",
        filetypes=(("Image files", "*.png;*.jpg;*.jpeg"), ("All files", "*.*"))
    )

    return image_paths

# start_detect_processing(img_path=start())
