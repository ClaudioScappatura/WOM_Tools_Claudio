import os
import shutil
import subprocess
import re
from collections import Counter
import natsort
import numpy as np
import photoshop.api as ps
import wmi
from photoshop.api import Application
import cv2
from paddleocr import PaddleOCR


PS_VERSION = None


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
        # todo capire cosa usare al posto di subprocess
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


# Salvataggio dell'immagine
def ps_save_image(initial_image: str, exit_psd=True):
    try:
        app = Application(version=PS_VERSION)
        doc = app.open(initial_image)
        file_name, file_extension = os.path.splitext(initial_image)
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
def ps_actions(ps_image: str, action_name: str,
               x_sx: float | int = 0, y_up: float | int = 0, x_dx: float | int = 0, y_down: float | int = 0):
    try:
        app = Application(version=PS_VERSION)
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
    except Exception as e:
        print(f"Errore durante l'esecuzione dell'azione: {e}")


def get_center(box):
    """Calcola il centro di un box."""
    x1, y1, x2, y2 = box
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2])


def get_size(box):
    """Calcola la dimensione di un box."""
    x1, y1, x2, y2 = box
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
                    x1, y1, x2, y2 = box
                    nx1, ny1, nx2, ny2 = new_box
                    new_boxes[i] = [min(x1, nx1), min(y1, ny1), max(x2, nx2), max(y2, ny2)]
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
def get_perimeter_colors(box, image, expand, tolerance):
    x1, y1, x2, y2 = expand_box(box, expand + 1, image)
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

        # Verifica se il colore dominante supera la soglia di tolleranza
        if dominant_percentage >= tolerance:
            return dominant_color
        else:

            return None
    else:
        return None


# In base al colore dei pixel analizzati, decide se riempire con il bianco o con il generative fill
def analyze_and_remove(path_image, result_ocr: list[list[tuple[str, None]]], img_binary=None, clear_all: bool = False, onomatopee: list | str = ""):
    try:
        if img_binary is None:
            img_binary = cv2.imread(path_image)
        #
        # # Parole da non pulire
        # lista_onomatopee = [
        #     "pow", "boom", "zap", "bam", "whoosh", "crash", "splash", "sizzle", "thump", "swish",
        #     "pop", "gulp", "tick-tock", "chomp", "zing", "buzz", "wham", "zoom", "crunch", "bang",
        #     "slam", "crack", "swoosh", "smash", "thud", "clang", "clink", "bloop", "ping", "ding",
        #     "clap", "rumble", "clatter", "flutter", "squeak", "squish", "screech", "roar", "hiss", "whack",
        #     "thwack", "whee", "whip", "knock", "ting", "rattle", "boing", "huff", "puff", "whisper",
        #     "giggle", "sigh", "gurgle", "sob", "burst", "drip", "crunchy", "plop", "shatter", "chirp",
        #     "twinkle", "glimmer", "glitter", "burst", "shimmer", "stomp", "stumble", "growl", "chuckle", "yawn",
        #     "thud", "tap", "rustle", "murmur", "rumble", "shuffle", "tremble", "rustle", "crackle", "clutch",
        #     "swoop", "pounce", "stab", "flutter", "jingle", "jangle", "whistle", "scuttle", "stomp", "crawl",
        #     "stretch", "snap", "twist", "whimper", "pitter-patter", "scamper", "squawk", "slither", "clamor", "swirl",
        #     "drumroll", "gong", "wail", "tinkle", "buzzing", "whirr", "hum", "zoom", "squelch", "gobble",
        #     "sizzle", "splash", "dribble", "swoosh", "bellow", "crunch", "hiccup", "crunch", "splatter", "chime",
        #     "creak", "groan", "rustle", "stomp", "zap", "babble", "chatter", "blare", "bump", "ding-dong",
        #     "giggle", "grumble", "slam", "snarl", "huff", "puff", "scorch", "tug", "wheeze", "wiggle",
        #     "squelch", "stumble", "whimper", "rumble", "throb", "clang", "ding", "clunk", "sniff", "shout",
        #     "cry", "scream", "mumble", "whack", "wheeze", "gasp", "sneak", "scamper", "splish-splash", "flutter",
        #     "glimpse", "sigh", "squeal", "tickle", "sprinkle", "gurgling", "thump", "stagger", "howl", "wobble",
        #     "twitch", "woop", "slurp", "hngh", "pwah", "aghh", "ang", "kyaa", "haah", "hangg", "haghh", "huh", "haeungh",
        #     "eup", "urghh", "heup", "keuk", "hah", "urgh", "ugh", "heupgh", "euppp", "hughh", "eut"]


        not_cleaned = []  # Parole da togliere con il Generative Fill
        for coord in result_ocr:
            tolerance = 0.88
            for repetition in range(10):
                for box in coord:
                    # TODO Capire come utilizzare Numpy
                    try:
                        # Controllo se la parola è una onomatopea
                        if not box[1][0].replace(".", "").replace("?", "").replace("!", "").lower() in onomatopee and box[1][1] >= 0.5:
                            x1, y1, x2, y2 = int(box[0][0][0]), int(box[0][0][1]), int(box[0][2][0]), int(box[0][2][1])
                            for exp in range(0, 8, 1):
                                result_color = get_perimeter_colors(box=[x1, y1, x2, y2], image=img_binary, expand=exp, tolerance=tolerance)
                                if result_color is not None:
                                    # Box circondato dallo stesso colore
                                    img_binary = cv2.rectangle(img_binary, (int(x1) - 5, int(y1) - 6), (int(x2) + 5, int(y2) + 6), (result_color[0], result_color[1], result_color[2]), -1)
                                    print(f"Test pulito: {box[1][0]} con Thres: {box[1][1]}")
                                    coord.remove(box)  # Rimozione parola pulita
                                    break
                            # La il box non è stato pulito
                            if repetition == 9 and box[1][1] >= 0.64:
                                not_cleaned.append([x1, y1, x2, y2])
                                print(f"Testo NON pulito -> {box[1][0]} con Thres: {box[1][1]}")
                    except Exception as e:
                        print(f"Errore durante l'elaborazione del box: {e}")
                if repetition == 9:
                    save_no_balloon_img(path_image, "/temp_clean/", img_binary)

            # Se si vuole pulire l'intera immagine e c'è ancora almeno una parola da togliere
            if clear_all and len(not_cleaned) > 0:
                try:
                    percorso = os.path.dirname(path_image)
                    file_name = os.path.basename(path_image)
                    # Merge dei box di testo adiacenti (facilita il fill di Photoshop)
                    merge_remaining_boxes = merge_boxes(not_cleaned, 1)
                    file_to_open = percorso + "/temp_clean/" + file_name
                    ps_actions(ps_image=file_to_open, action_name="start")
                    for coords in merge_remaining_boxes:
                        ps_actions(ps_image=file_to_open, action_name="selection", x_sx=coords[0], y_up=coords[1], x_dx=coords[2], y_down=coords[3])
                        ps_actions(action_name="generative_fill", ps_image=file_to_open)
                    ps_save_image(file_to_open)
                    return True

                except Exception as e:
                    print(f"Errore durante il merge dei box di testo oppure generative fill: {e}")
            else:
                return False
    except Exception as e:
        print(f"Errore durante l'analisi e rimozione delle parole: {e}")
        return None


# Salva in 'temp_clean' le immagini con i balloon puliti
def save_no_balloon_img(img_path: str, dest_folder: str, cv2_img):
    percorso = os.path.dirname(img_path)
    print("Directory:", percorso)
    if not os.path.exists(percorso + "/" + dest_folder):
        os.makedirs(percorso + "/" + dest_folder)

    file_con_estensione = os.path.basename(img_path)
    print("Nome con estensione:", file_con_estensione)
    # Salva l'immagine
    cv2.imwrite(percorso + f"/{dest_folder}/" + file_con_estensione, cv2_img)


# Funzione che inserisce in un nuovo PSD l'immagine RAW e quella Auto-Cleaned
def assemble_psd(images_path: str, clean_path: str = "", raw_files: list = None, save_path: str | None = None):
    try:
        app = Application(version=PS_VERSION)
        clean_files = get_images_list(images_path + clean_path)[0]

        for raw, clean in zip(raw_files, clean_files):
            doc2 = app.open(clean)
            doc2.activeLayer.name = "AutoClean"
            doc2.selection.copy()

            doc1 = app.open(raw)
            doc1.activeLayer.name = "RAW"
            doc1.paste()

            if save_path is None:
                save_path = images_path
            output_folder = save_path + "/PSD_Cleaned"
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)

            output_path = os.path.join(output_folder, os.path.basename(raw))
            doc1.saveAs(output_path, ps.PhotoshopSaveOptions(), asCopy=False)

            doc1.close()
            doc2.close()
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


# Analizza l'input (cartella o file), riconosce il testo, ricompone e salva il PSD
def start_detect_processing(gpu: bool, clear_all: bool, save_and_exit: bool, img_path: str | list, destination_path: str | None = None):
    try:

        ocr = PaddleOCR(use_angle_cls=True, lang='en', ocr_order_method="det_ar", use_gpu=gpu,
            det_db_score_mode="slow", max_text_length=200, cpu_math_library_num_threads=4, use_mp=True,
            det_db_thresh=0.4, det_limit_side_len=17000, det_db_unclip_ratio=1.5, det_db_box_thresh=0.68, det_pse_box_thresh=0.80, e2e_pgnet_mode='accurate')

        img_path_list_to_clean, is_dir = get_images_list(img_path)
        img_path = os.path.dirname(img_path_list_to_clean[0])

        for img in img_path_list_to_clean:
            pred_groups = ocr.ocr(img, cls=True)
            if analyze_and_remove(path_image=img, result_ocr=pred_groups, clear_all=clear_all):
                ps_save_image(img, True)

        temp_path = "/temp_clean"
        assemble_psd(img_path, raw_files=img_path_list_to_clean, clean_path=temp_path, save_path=destination_path)
        remove_other_dir(img_path)
    except Exception as e:
        print(f"Errore durante l'avvio del processo di rilevamento e elaborazione: {e}")
