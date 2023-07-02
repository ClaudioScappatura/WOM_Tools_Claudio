

import torch
import webbrowser
import ImgCleaner
import ImgConverter
import PsdCreator
from tkinter import *
from tkinter import filedialog
from image_slicer import *
from image_utilities import *
import threading
import natsort
from packaging import version
import customtkinter as ctk

# Istanza del creatore di PSD
psd_creator_instance = PsdCreator
img_converter_instance = ImgConverter
image_paths = None
image_paths_2 = None
path_save = None
GPU = False


def start_clean():
    ImgCleaner.start_detect_processing(GPU, radio_type_clean.get(), radio_psd_state.get(), image_paths)


def manage_input(event):
    t_area_string = manual_path_var.get()
    print(len(t_area_string))
    if len(t_area_string) > 1:
        window.select_file_cleaner_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    else:
        window.select_file_cleaner_bt.configure(state=ACTIVE, fg_color=("#3B8ED0", "#1F6AA5"))


def sel_type_input():
    if radio_select_file_cleaner.get() == 2:
        window.select_file_cleaner_bt.configure(text="Seleziona la cartella")
    else:
        window.select_file_cleaner_bt.configure(text="Seleziona le immagini")


def sel_files_cleaner(type_sel: int = None):
    global image_paths

    if radio_select_file_cleaner.get() == 2:
        # Cartella
        image_paths = filedialog.askdirectory(
            title="Scegli la cartella con immagini da pulire",
        )
    elif radio_select_file_cleaner.get() == 1:
        # Immagini
        image_paths = filedialog.askopenfilenames(
            title="Scegli la prima immagine",
            filetypes=(("Image files", "*.png;*.jpg;*.jpeg"), ("All files", "*.*"))
        )
    if len(image_paths) == 0:
        window.process_cleaner_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    else:
        window.process_cleaner_bt.configure(state=ACTIVE, fg_color=("#3B8ED0", "#1F6AA5"))


def type_clean_descr():
    all_descr = "PULISCI TUTTO:\n L'algoritmo cercherà di ripulire il testo\n presente nei balloon e sulle " \
                "immagini.\nDisponibile con PS v24.6.* e successive "
    balloon_descr = "PULISCI BALLOON:\n L'algoritmo cercherà di ripulire \nsolamente il testo presente nei balloon\n" \
                    "NOTA: Funzionante solo su balloon bianchi"
    if radio_type_clean.get():
        # tutto
        window.clear_type_descr_lab.configure(text=all_descr)
    elif not radio_type_clean.get():
        # balloon
        window.clear_type_descr_lab.configure(text=balloon_descr)


def photoshop_finder():
    target_version = "24.6.0.2185"
    version_ps = ImgCleaner.get_ps_version()
    # version_ps = "24.5.0.3334"
    # version_ps = None
    if version_ps is None:
        window.photoshop_version_lab.configure(text="Photoshop non risulta essere installato. Impossibile continuare.")
        return None
    else:
        window.photoshop_version_lab.configure(text="La tua versione di Photoshop: " + version_ps)
        return version.Version(version_ps) >= version.Version(target_version)


def gpu_allow():
    if ImgCleaner.check_nvidia_gpu():
        lab_text = "GPU: NVIDIA"
        if torch.cuda.is_available():
            lab_text += "\n ACCELLERAZIONE GRAFICA ABILITATA"
            window.url_cuda_lab.destroy()
            var_return = True
        else:
            lab_text += "\n Per abilitare l'accellerazione grafica, scarica CUDA Toolkit 11.8"
            window.url_cuda_lab.configure(text="CLICCA QUI PER SCARICARE CUDA", text_color='white', justify='center')
            var_return = False
        window.gpu_disp_lab.configure(text=lab_text, text_color='white')
        return var_return
    else:
        window.gpu_disp_lab.configure(text="La tua GPU non supporta l'accelerazione grafica\nL'elaborazione sarà più "
                                           "lenta", justify='center')
        window.url_cuda_lab.destroy()
        return False


# Scelta delle immagini da trasformare in PSD
def select_files():
    global image_paths
    global image_paths_2

    # modalità immagini multiple
    if radio_value.get() == 2:
        # Seleziona le immagini da elaborare
        image_paths = filedialog.askopenfilenames(
            title="Scegli le immagini",
            filetypes=(("Image files", "*.png;*.jpg;*.jpeg"), ("All files", "*.*"))  # Tipi di file immagine accettati
        )
        if len(image_paths) > 0:
            window.save_dest_psd_bt.configure(state=ACTIVE, fg_color=("#3B8ED0", "#1F6AA5"))

    # modalità due immagini
    if radio_value.get() == 1:
        # Seleziona al massimo due immagini
        image_paths = filedialog.askopenfilename(
            title="Scegli la prima immagine",
            filetypes=(("Image files", "*.png;*.jpg;*.jpeg"), ("All files", "*.*"))
        )
        if len(image_paths) > 0:
            image_paths_2 = filedialog.askopenfilename(
                title="Scegli la seconda immagini",
                filetypes=(("Image files", "*.png;*.jpg;*.jpeg"), ("All files", "*.*"))
            )

            # se i path di entrambe le immagini non sono vuoti
            if len(image_paths_2) > 0:
                window.save_dest_psd_bt.configure(state=ACTIVE, fg_color=("#3B8ED0", "#1F6AA5"))
            else:
                # Scelte meno di due immagini. ERRORE
                tk.messagebox.showerror("Errore", "Devi selezionare entrambe le immagini")
                window.save_dest_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
                window.save_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
                return


# scelta del percorso di salvataggio
def dir_save_psd():
    global path_save
    path_save = filedialog.askdirectory(
        title="Scegli dove salvare il PSD",
    )
    window.save_psd_bt.configure(state=ACTIVE, fg_color=("#3B8ED0", "#1F6AA5"))


def psd_image_save():
    # Progress bar
    window.p = ctk.CTkProgressBar(window.builder_frame, width=250, mode="determinate", orientation="horizontal")
    window.p.grid(row=8, column=3, columnspan=5)
    # Label di elaborazione
    window.working_build_lab = ctk.CTkLabel(window.builder_frame, text="Photoshop sta elaborando....",
        font=("Courier New", 14, "bold"))
    window.working_build_lab.grid(row=7, column=3, columnspan=5, pady=10)
    p_step = 1 / len(image_paths)
    psd_creator_instance.psd_image_save(window.working_build_lab, p_step, window.p, radio_value.get(), image_paths,
        image_paths_2, path_save)
    tk.messagebox.showinfo("FATTO!", "Il file è stato creato con successo!")
    window.save_dest_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    window.save_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    window.p.destroy()
    window.working_build_lab.destroy()


# Mostra la descrizione dei radio button
# Disattiva i pulsanti ogni volta che si cambia voce del radio button
def description_radio_button_PsdConverter():
    window.save_dest_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    window.save_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    window.definition_functions_lab.configure(text=psd_creator_instance.multiple_def_function(radio_value.get()))


# Scelta file da convertire
def select_files_to_convert():
    global image_paths

    # Seleziona le immagini da elaborare
    image_paths = filedialog.askopenfilenames(
        title="Scegli le immagini",
        filetypes=(("Image files", "*.png;*.jpg;*.jpeg;*.psd"), ("All files", "*.*"))  # Tipi di file immagine accettati
    )
    # Se scelta almeno una immagine
    if len(image_paths) > 0:
        window.select_conv_save_bt.configure(state=ACTIVE, fg_color=("#3B8ED0", "#1F6AA5"))
    else:
        window.select_conv_save_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))


# Scelta destinazione di salvataggio file convertiti
def select_conv_save_dir():
    global path_save
    # scelta percorso
    path_save = filedialog.askdirectory(
        title="Scegli dove salvare i file convertiti",
    )
    # Se scelto il percorso
    if len(path_save) > 0:
        window.conv_run_bt.configure(state=ACTIVE, fg_color=("#3B8ED0", "#1F6AA5"))
    else:
        window.conv_run_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))


# Conversione immagini/PSD
def conv_image_start():
    # Progress bar
    window.p = ctk.CTkProgressBar(window.converter_frame, width=250, mode="determinate", orientation="horizontal")
    window.p.grid(row=9, column=3, columnspan=5)
    # Label di elaborazione
    window.working_conv_lab = ctk.CTkLabel(window.converter_frame, text="Elaborazione delle immagini...",
        font=("Courier New", 14, "bold"))
    window.working_conv_lab.grid(row=8, column=3, columnspan=5)
    window.p.set(0.01)
    window.update_idletasks()
    # Conversione immagini
    img_converter_instance.conv_image_start(window, window.p, image_paths, path_save, window.format_cb.get())
    # Conversione riuscita
    tk.messagebox.showinfo("CONVERSIONE RIUSCITA", "I file sono stati convertiti con successo!")
    window.working_conv_lab.configure(text_color=('gray92', 'gray14'))
    window.conv_run_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    window.select_conv_save_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
    window.format_cb.set("JPG")
    window.p.destroy()


def save_in(folder_path: str, file: Image.Image, name: str, save_as: str | None = ".png"):
    file.save(f"{folder_path}/{name}{save_as}")


def is_config():
    # todo controllo sul numero
    desired_height = window.desired_height_t_area.get()
    max_height = window.max_height_t_area.get()
    min_height = window.min_height_t_area.get()


    if not desired_height.isnumeric():
        print("Altezza desiderata non valida, valore preso in considerazione 10000")
        desired_height = 10000
    if (not max_height.isnumeric()) or (max_height.isnumeric() and int(max_height) > desired_height):
        print("Altezza massima non valida, valore preso in considerazione 10000")
        max_height = 10000
    if not min_height.isnumeric() or min_height >= min(max_height, desired_height):
        print("Altezza minima non valida, valore preso in considerazione 1000")
        min_height = 1000

    files = os.listdir(image_paths)
    files = natsort.natsorted(files)

    images: list[Image.Image] = [
        get_image(f"{image_paths}/{x}")
        for x in files
        if os.path.isfile(f"{image_paths}/{x}") and x.endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]

    desired_height = int(desired_height)
    max_height = int(max_height)
    min_height = int(min_height)

    # Progresso bar
    window.p = ctk.CTkProgressBar(window.slicer_frame, width=250, mode="determinate", orientation="horizontal")
    window.p.grid(row=12, column=3, columnspan=5)
    print(len(images))

    # Label di elaborazione
    window.working_lab = ctk.CTkLabel(window.slicer_frame, text="Elaborazione delle immagini...",
        font=("Courier New", 14, "bold"))
    window.working_lab.grid(row=11, column=3, columnspan=5)
    # Valori della progress bar vanno da 0 a 1
    p_incr = 1 / len(images)
    out = image_slicer(p_incr, window.p, window, images, desired_height, min_height, max_height)
    window.working_lab.configure(text_color=('gray92', 'gray14'))
    # Label di salvataggio
    window.loading_lab = ctk.CTkLabel(window.slicer_frame, text="Salvataggio in corso...",
        font=("Courier New", 14, "bold"))
    window.loading_lab.grid(row=13, column=3, columnspan=5)

    window.update()

    if not os.path.exists(f"{image_paths}/sliced/"):
        os.makedirs(f"{image_paths}/sliced/")

    threads = []
    for pos, img in enumerate(out):
        new_thread = threading.Thread(target=save_in, args=([image_paths + "/sliced", img, str(pos + 2)]))
        new_thread.start()
        window.update()
        threads.append(new_thread)

    for t in threads:
        t.join()

    for pos, _ in enumerate(threads):
        threads[pos] = None

    tk.messagebox.showinfo("TAGLIO RIUSCITO", "Immagini tagliate con successo")
    window.p.destroy()
    window.loading_lab.destroy()
    window.cut_img_bt.configure(fg_color=("gray75", "gray25"), state=DISABLED)


def select_directory_slicer():
    global image_paths

    # Seleziona le immagini da elaborare
    image_paths = filedialog.askdirectory(
        title="Scegli la cartella con le immagini",
    )
    if len(image_paths) > 0:
        window.cut_img_bt.configure(state=ACTIVE)
        window.cut_img_bt.configure(fg_color=("#3B8ED0", "#1F6AA5"))
    else:
        window.cut_img_bt.configure(state=DISABLED)
        window.cut_img_bt.configure(fg_color=("gray75", "gray25"))


# Click sulla text area dello slicer
def click_max_height(event):
    manage_slicer_text_box("Max")


# Click sulla text area dello slicer
def click_min_height(event):
    manage_slicer_text_box("Min")


# Click sulla text area dello slicer
def click_desired_height(event):
    manage_slicer_text_box("Desired")


# Gestisce il contenuto delle text area quando cliccate
def manage_slicer_text_box(name_click: str):
    if name_click == "Desired":
        # Si svuota la text area
        if "Default" in window.desired_height_t_area.get():
            window.desired_height_t_area.delete(0, END)
            window.max_height_t_area.insert(0, "")
            window.desired_height_t_area.configure(text_color="gray75")
    else:
        # Si inserisce il valore di default se rimasta vuota
        if window.desired_height_t_area.get().isspace() or window.desired_height_t_area.get() == "":
            window.desired_height_t_area.insert(index=0, string="Default: 10000")
            window.desired_height_t_area.configure(text_color="gray45")

    if name_click == "Max":
        # Si svuota la text area
        if "Default" in window.max_height_t_area.get():
            window.max_height_t_area.delete(0, END)
            window.max_height_t_area.insert(0, "")
            window.max_height_t_area.configure(text_color="gray75")
    else:
        # Si inserisce il valore di default se rimasta vuota
        if window.max_height_t_area.get().isspace() or window.max_height_t_area.get() == "":
            window.max_height_t_area.insert(index=0, string="Default: 10000")
            window.max_height_t_area.configure(text_color="gray45")

    if name_click == "Min":
        # Si svuota la text area
        if "Default" in window.min_height_t_area.get():
            window.min_height_t_area.delete(0, END)
            window.min_height_t_area.insert(0, "")
            window.min_height_t_area.configure(text_color="gray75")
    else:
        # Si inserisce il valore di default se rimasta vuota
        if window.min_height_t_area.get().isspace() or window.min_height_t_area.get() == "":
            window.min_height_t_area.insert(index=0, string="Default: 10000")
            window.min_height_t_area.configure(text_color="gray45")


def callback(url):
    if len(window.url_cuda_lab.cget("text")) > 0:
        webbrowser.open_new_tab(url)


# Richiama il frame selezionato
def slicer_menu_button_event():
    select_frame_by_name("Slicer")


# Richiama il frame selezionato
def converter_menu_button_event():
    select_frame_by_name("Converter")


# Richiama il frame selezionato
def builder_menu_button_event():
    select_frame_by_name("Builder")


def cleaner_menu_button_event():
    select_frame_by_name("Cleaner")


# Mostra il frame chiamato
def select_frame_by_name(name):
    # Evidenzia bottone menu quando premuto
    window.slicer_menu.configure(fg_color=("gray75", "gray25") if name == "Slicer" else "transparent")
    window.psd_builder_menu.configure(fg_color=("gray75", "gray25") if name == "Builder" else "transparent")
    window.converter_menu.configure(fg_color=("gray75", "gray25") if name == "Converter" else "transparent")
    window.cleaner_menu.configure(fg_color=("gray75", "gray25") if name == "Cleaner" else "transparent")

    # Mostra il frame selezionato
    if name == "Slicer":
        window.slicer_frame.grid(row=0, column=1, sticky="nsew")
    else:
        window.slicer_frame.grid_forget()
    if name == "Converter":
        window.converter_frame.grid(row=0, column=1, sticky="nsew")
    else:
        window.converter_frame.grid_forget()
    if name == "Builder":
        window.builder_frame.grid(row=0, column=1, sticky="nsew")
    else:
        window.builder_frame.grid_forget()
    if name == "Cleaner":
        window.cleaner_frame.grid(row=0, column=1, sticky="nsew")
    else:
        window.cleaner_frame.grid_forget()


window = ctk.CTk()
window.iconbitmap("WOM_Logo.ico")
window.title("WOM Toolkit-v23.1")
window.geometry("700x600")
window.resizable(False, False)

# set grid layout 1x2
window.grid_rowconfigure(0, weight=1)
window.grid_columnconfigure(1, weight=1)

# create navigation frame
window.navigation_frame = ctk.CTkFrame(window, corner_radius=0)
window.navigation_frame.grid(row=0, column=0, sticky="nsew")
window.navigation_frame.grid_rowconfigure(5, weight=1)

# Label "WOM_TOOLS"
window.navigation_frame_label = ctk.CTkLabel(window.navigation_frame, text="WOM_TOOLS", compound="left",
    font=("Courier New", 18, "bold"))
window.navigation_frame_label.grid(row=0, column=0, padx=20, pady=20)

# Bottone "Slicer" in barra di navigazione
window.slicer_menu = ctk.CTkButton(window.navigation_frame, corner_radius=0, height=40, border_spacing=10,
    text="Slicer", fg_color="transparent", text_color=("gray10", "gray90"),
    hover_color=("gray70", "gray30"), anchor="w",
    font=("Courier New", 15, "bold"),
    command=slicer_menu_button_event)
window.slicer_menu.grid(row=1, column=0, sticky="ew", pady=0, padx=10)

# Bottone "Converter" in barra di navigazione
window.converter_menu = ctk.CTkButton(window.navigation_frame, corner_radius=0, height=40, border_spacing=10,
    text="Converter", fg_color="transparent", text_color=("gray10", "gray90"),
    hover_color=("gray70", "gray30"), anchor="w",
    font=("Courier New", 15, "bold"), command=converter_menu_button_event)
window.converter_menu.grid(row=2, column=0, sticky="ew", pady=0, padx=10)

# Bottone "PSD Builder" in barra di navigazione
window.psd_builder_menu = ctk.CTkButton(window.navigation_frame, corner_radius=0, height=40, border_spacing=10,
    text="PSD Builder", fg_color="transparent", text_color=("gray10", "gray90"),
    hover_color=("gray70", "gray30"), anchor="w",
    font=("Courier New", 15, "bold"), command=builder_menu_button_event)
window.psd_builder_menu.grid(row=3, column=0, sticky="ew", pady=0, padx=10)

# Bottone 'Cleaner' in barra di navigazione
window.cleaner_menu = ctk.CTkButton(window.navigation_frame, corner_radius=0, height=40, border_spacing=10,
    text="Cleaner", fg_color="transparent", text_color=("gray10", "gray90"),
    hover_color=("gray70", "gray30"), anchor="w",
    font=("Courier New", 15, "bold"), command=cleaner_menu_button_event)
window.cleaner_menu.grid(row=4, column=0, sticky="ew", pady=0, padx=10)

# Creazione frame Slicer
window.slicer_frame = ctk.CTkFrame(window, corner_radius=0, fg_color="transparent")
window.slicer_frame.grid_columnconfigure(5, weight=1)
window.slicer_frame.grid_rowconfigure(14, weight=1)
# Label "IMAGE SLICER"
window.slicer_frame_label = ctk.CTkLabel(window.slicer_frame, text="IMAGE SLICER", font=("Courier New", 30, "bold"))
window.slicer_frame_label.grid(row=0, column=3, columnspan=5, pady=20, sticky="WE")
# Label di descrizione
window.slider_descr_lab = ctk.CTkLabel(window.slicer_frame, text="Taglia le immagini in determinati punti",
    font=("Courier New", 16))
window.slider_descr_lab.grid(row=1, column=3, columnspan=5, sticky="WE")
# Bottone "Scegli i file"
window.select_file_slicer_bt = ctk.CTkButton(window.slicer_frame, text="Scegli la cartella", font=("Courier New", 16),
    command=select_directory_slicer)
window.select_file_slicer_bt.grid(row=2, column=3, columnspan=5, pady=20)
# Label di "Altezza desiderata"
window.desired_height_lab = ctk.CTkLabel(window.slicer_frame, text="Altezza desiderata", font=("Courier New", 14))
window.desired_height_lab.grid(row=3, column=3, columnspan=5)
# TextArea di "Altezza desiderata"
ctk.CTkLabel(window.slicer_frame, font=("Courier New", 12))
window.desired_height_t_area = ctk.CTkEntry(window.slicer_frame)
window.desired_height_t_area.grid(row=4, column=3, columnspan=5)
window.desired_height_t_area.insert(index=0, string="Default: 10000")
window.desired_height_t_area.configure(text_color="gray45")
window.desired_height_t_area.bind('<Button-1>', command=click_desired_height)

# Label di "Altezza minima"
window.min_height_lab = ctk.CTkLabel(window.slicer_frame, text="Altezza minima", font=("Courier New", 14))
window.min_height_lab.grid(row=5, column=3, columnspan=5)
# TextArea di "Altezza minima"
ctk.CTkLabel(window.slicer_frame, font=("Courier New", 12))
window.min_height_t_area = ctk.CTkEntry(window.slicer_frame)
window.min_height_t_area.grid(row=6, column=3, columnspan=5)
window.min_height_t_area.insert(index=0, string="Default: 1000")
window.min_height_t_area.configure(text_color="gray45")
window.min_height_t_area.bind('<Button-1>', command=click_min_height)

# Label di "Altezza massima"
window.max_height_lab = ctk.CTkLabel(window.slicer_frame, text="Altezza massima", font=("Courier New", 14))
window.max_height_lab.grid(row=7, column=3, columnspan=5)
# TextArea di "Altezza massima"
ctk.CTkLabel(window.slicer_frame, font=("Courier New", 12))
window.max_height_t_area = ctk.CTkEntry(window.slicer_frame)
window.max_height_t_area.grid(row=8, column=3, columnspan=5)
window.max_height_t_area.insert(index=0, string="Default: 10000")
window.max_height_t_area.configure(text_color="gray45")
window.max_height_t_area.bind('<Button-1>', command=click_max_height)

# Bottone "Taglia"
window.cut_img_bt = ctk.CTkButton(window.slicer_frame, text="TAGLIA",
    font=("Courier New", 20), command=is_config)
window.cut_img_bt.configure(window.slicer_frame, fg_color=("gray75", "gray25"))
window.cut_img_bt.grid(row=10, column=3, columnspan=5, pady=20)
window.cut_img_bt.configure(width=200)
window.cut_img_bt.configure(state=DISABLED)
# Print del colore del bottone
print(window.select_file_slicer_bt.cget('fg_color'))
# ----------------------------------------------- PSD/IMG CONVERTER--------------------------------------------------
# Creazione frame Converter
window.converter_frame = ctk.CTkFrame(window, corner_radius=0, fg_color="transparent")
window.converter_frame.grid_columnconfigure(5, weight=1)
window.converter_frame.grid_rowconfigure(10, weight=1)

# Titolo CONVERSIONE PSD - JPG
window.conversion_title_lab = ctk.CTkLabel(window.converter_frame, text="CONVERTITORE di PSD/IMG",
    font=("Courier New", 30, "bold"))
window.conversion_title_lab.grid(row=0, column=3, columnspan=5, pady=20)
# Label di spiegazione conversione
window.conv_descr_lab = ctk.CTkLabel(window.converter_frame,
    text="Questo è un convertitore di immagini e file Adobe",
    font=("Courier New", 16))
window.conv_descr_lab.grid(row=2, column=3, columnspan=5)
# Pulsante scelta file da convertire
window.select_conv_file_bt = ctk.CTkButton(window.converter_frame, text="Scegli i file",
    font=("Courier New", 16), command=select_files_to_convert)
window.select_conv_file_bt.grid(row=3, column=3, columnspan=5, pady=20)
window.select_conv_file_bt.configure(height=30, width=200)
# Pulsante scelta dove salvare file convertiti
window.select_conv_save_bt = ctk.CTkButton(window.converter_frame, text="Scegli dove salvare",
    font=("Courier New", 16), command=select_conv_save_dir)
window.select_conv_save_bt.grid(row=4, column=3, columnspan=5)
window.select_conv_save_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
# Label scelta formato
window.conv_def_lab = ctk.CTkLabel(window.converter_frame, text="Scegliere il formato di conversione",
    font=("Courier New", 16))
window.conv_def_lab.grid(row=5, column=3, columnspan=5, pady=20)
# Combobox per scelta formato di conversione
window.format_cb = ctk.CTkComboBox(window.converter_frame, state="readonly")
window.format_cb.configure(state=NORMAL, values=["JPG", "PNG", "PPM", "TIFF", "BMP", "GIF"])
window.format_cb.grid(row=6, column=3, columnspan=5)
# Formato di default
window.format_cb.set("JPG")
# Pulsante di inizio conversione
window.conv_run_bt = ctk.CTkButton(window.converter_frame, text="CONVERTI", font=("Courier New", 20),
    command=conv_image_start)
window.conv_run_bt.configure(width=200)
window.conv_run_bt.grid(row=7, column=3, columnspan=5, pady=40)
window.conv_run_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))

# --------------------------------------------------- PSD BUILDER -----------------------------------------------
# Creazione frame PSD Builder
window.builder_frame = ctk.CTkFrame(window, corner_radius=0, fg_color="transparent")
window.builder_frame.grid_columnconfigure(5, weight=1)
window.builder_frame.grid_rowconfigure(10, weight=1)

# Titolo del creatore di PSD
window.create_psd_lab = ctk.CTkLabel(window.builder_frame, text="CREA PSD DA IMG", font=("Courier New", 30, "bold"))
window.create_psd_lab.grid(row=0, column=3, columnspan=5, pady=20)
# Bottone per scegliere i files
window.select_files_psd_bt = ctk.CTkButton(window.builder_frame, text="Scegli i file", font=("Courier New", 16),
    command=select_files)
window.select_files_psd_bt.grid(row=1, column=3, columnspan=5)
window.select_files_psd_bt.configure(height=30, width=180)
# Valore radio button cliccato
radio_value = IntVar()
# Bottone scelta percorso salvataggio PSD
window.multiple_img_rb = ctk.CTkRadioButton(window.builder_frame, variable=radio_value, text="Multiple", value=2,
    font=("Courier New", 18),
    command=description_radio_button_PsdConverter)
window.multiple_img_rb.grid(row=2, column=3, columnspan=5, pady=20)
# Selezione di default RB
window.multiple_img_rb.select()

# Definizione radio button
window.two_img_rb = ctk.CTkRadioButton(window.builder_frame, text="Due immagini", variable=radio_value, value=1,
    font=("Courier New", 18),
    command=description_radio_button_PsdConverter)
window.two_img_rb.grid(row=3, column=3, columnspan=5, sticky="N")
# Label che spiega il funzionamento legato ai radio button
window.definition_functions_lab = ctk.CTkLabel(window.builder_frame, font=("Courier New", 16))
window.definition_functions_lab.grid(row=4, column=3, columnspan=5, pady=20)
# Bottone per scelta destinazione salvataggio
window.save_dest_psd_bt = ctk.CTkButton(window.builder_frame, text="Scegli dove salvare", font=("Courier New", 16),
    command=dir_save_psd)
window.save_dest_psd_bt.grid(row=5, column=3, columnspan=5, pady=20)
window.save_dest_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
# Pulsante di salvataggio
window.save_psd_bt = ctk.CTkButton(window.builder_frame, text="SALVA", font=("Courier New", 20), command=psd_image_save)
window.save_psd_bt.grid(row=6, column=3, columnspan=5)
window.save_psd_bt.configure(width=200)
window.save_psd_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))
description_radio_button_PsdConverter()

# ------------------------------------------- IMG CLEANER ---------------------------------------------
# Creazione frame Slicer
window.cleaner_frame = ctk.CTkFrame(window, corner_radius=0, fg_color="transparent")
window.cleaner_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
# window.slicer_frame.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13), weight=1)
window.grid_propagate(True)
# Label "IMAGE SLICER"
window.cleaner_frame_label = ctk.CTkLabel(window.cleaner_frame, text="IMAGE CLEANER", font=("Courier New", 30,
                                                                                            "bold"))
window.cleaner_frame_label.grid(row=0, column=0, columnspan=5, pady=20, sticky="WESN")
# Label di descrizione
window.cleaner_descr_lab = ctk.CTkLabel(window.cleaner_frame, text="Rimuove il testo dalle immagini",
    font=("Courier New", 16))
window.cleaner_descr_lab.grid(row=1, column=0, columnspan=5, sticky="WESN")
# Bottone "Scegli"
window.select_file_cleaner_bt = ctk.CTkButton(window.cleaner_frame, font=("Courier New", 16),
    command=sel_files_cleaner)
window.select_file_cleaner_bt.grid(row=3, column=0, columnspan=5, padx=(0, 20), pady=(10, 15), sticky="NS")
# Checkbox per "Indirizzo manuale"
window.select_path_cleaner_lab = ctk.CTkLabel(window.cleaner_frame, text="Path:", font=("Courier New", 16))
# window.select_path_cleaner_lab.grid(row=3, column=0, sticky="E", padx=(0, 20), pady=(10, 0))
# TextArea per "Indirizzo manuale"
manual_path_var = StringVar()
window.insert_path_cleaner_t_area = ctk.CTkEntry(window.cleaner_frame, font=("Courier New", 12),
                                                 textvariable=manual_path_var)
window.insert_path_cleaner_t_area.bind('<Key>', manage_input)
window.insert_path_cleaner_t_area.bind('<Enter>', manage_input)
# Radio buttons
radio_select_file_cleaner = IntVar()
# Radio bt scegli cartella
window.dir_sel_rb = ctk.CTkRadioButton(window.cleaner_frame, variable=radio_select_file_cleaner, text="Cartella", value=2,
    font=("Courier New", 12), command=sel_type_input)
window.dir_sel_rb.grid(row=2, column=0, columnspan=2, pady=20, sticky="E")
# Radio bt scegli immagini
window.img_sel_rb = ctk.CTkRadioButton(window.cleaner_frame, text="Immagini", variable=radio_select_file_cleaner,
                                       value=1, font=("Courier New", 12), command=sel_type_input )
window.img_sel_rb.grid(row=2, column=3, columnspan=2, pady=20, sticky="W")
# Selezione di default RB
window.dir_sel_rb.select()
sel_type_input()
# Label sull'accelerazione grafica
window.gpu_disp_lab = ctk.CTkLabel(window.cleaner_frame, text="", font=("Courier New", 14))
window.gpu_disp_lab.grid(row=4, column=0, columnspan=5, pady=(10, 0), sticky="WESN")
# Label URL per CUDA
window.url_cuda_lab = ctk.CTkLabel(window.cleaner_frame, text="", font=("Courier New", 14, 'underline'))
window.url_cuda_lab.grid(row=5, column=0, columnspan=5, pady=(10, 20), sticky="WESN")
window.url_cuda_lab.bind("<Button-1>", lambda e:
callback("https://developer.nvidia.com/cuda-11-8-0-download-archive"))
GPU = gpu_allow()

# Radio buttons
radio_type_clean = BooleanVar()
# Radio bt pulisci balloons
window.clear_balloon_rb = ctk.CTkRadioButton(window.cleaner_frame, variable=radio_type_clean, text="Pulisci solo "
                                                                                                   "balloons", value=False,
    font=("Courier New", 12), command=type_clean_descr)
window.clear_balloon_rb.grid(row=7, column=0, columnspan=2, sticky="EN")
# Radio bt pulisci tutto il testo
window.clear_all_rb = ctk.CTkRadioButton(window.cleaner_frame, text="Pulisci tutto", variable=radio_type_clean, value=True,
    font=("Courier New", 12), command=type_clean_descr)
window.clear_all_rb.grid(row=7, column=3, columnspan=2, sticky="WN")

# Label spiegazione della pulizia
window.clear_type_descr_lab = ctk.CTkLabel(window.cleaner_frame, font=("Courier New", 15), text_color="white", text="")
window.clear_type_descr_lab.grid(row=8, column=0, columnspan=5, pady=(15, 0), sticky="WESN")

# Label Photoshop version
window.photoshop_version_lab = ctk.CTkLabel(window.cleaner_frame, text="", font=("Courier New", 14))
window.photoshop_version_lab.grid(row=6, column=0, columnspan=5, sticky="WENS", pady=(20, 10))

# Radio buttons
radio_psd_state = BooleanVar()
# Radio bt pulisci balloons
window.save_psd_rb = ctk.CTkRadioButton(window.cleaner_frame, variable=radio_psd_state, text="Lascia aperti i PSD",
    value=False,
    font=("Courier New", 12))  # todo inserire commando
window.save_psd_rb.grid(row=9, column=0, columnspan=2, sticky="EN", pady=(20, 0))
window.save_psd_rb.configure(state=DISABLED)
# Radio bt pulisci tutto il testo
window.close_psd_rb = ctk.CTkRadioButton(window.cleaner_frame, text="Salva e chiudi i PSD", variable=radio_psd_state,
    value=True, font=("Courier New", 12))  # todo ins command?
window.close_psd_rb.grid(row=9, column=3, columnspan=2, sticky="WN", pady=(20, 0))

# Verifica della presenza e versione di Photoshop
ps_version = photoshop_finder()
if ps_version is None:
    # Nessun Photoshop
    window.clear_balloon_rb.configure(state=DISABLED)
    window.clear_all_rb.configure(state=DISABLED)
    window.cleaner_descr_lab.destroy()
    window.save_psd_rb.configure(state=DISABLED)
    window.close_psd_rb.configure(state=DISABLED)
elif not ps_version:
    # Versione PS senza Generative Fill
    window.clear_balloon_rb.select()
    type_clean_descr()
    window.clear_all_rb.configure(text=" " + window.clear_all_rb.cget("text") + "\n(solo PS >= v2.6)", state=DISABLED)
    window.close_psd_rb.select()
else:
    # Photoshop con Generative fill
    window.clear_balloon_rb.select()
    type_clean_descr()
    window.close_psd_rb.select()



# Pulsante ELABORA
window.process_cleaner_bt = ctk.CTkButton(window.cleaner_frame, text="ELABORA IMMAGINI", font=("Courier New", 16),
    width=200, command=start_clean)  # todo ins comando
window.process_cleaner_bt.grid(row=10, column=0, columnspan=5, sticky="ns", pady=(25,0))
window.process_cleaner_bt.configure(state=DISABLED, fg_color=("gray75", "gray25"))

# Set default frame "Img Converter"
select_frame_by_name("Cleaner")

window.mainloop()
