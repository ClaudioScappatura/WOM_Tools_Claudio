import os
from PIL import Image
from psd_tools import PSDImage
from tkinter import messagebox
import tkinter as tk
from photoshop import Session


# Conversione immagini/PSD
def conv_image_start(window, pr, image_paths, save_path, conversion_format):
    p_step = 1 / len(image_paths)
    i = 0
    show = False
    # Conversione di ogni file immagine scelto
    for img_f in image_paths:
        i += 1
        pr.set(i * p_step)
        # Creazione posizione di salvataggio in base al formato scelto
        file_name, file_extension = os.path.splitext(img_f)
        nameImg = os.path.splitext(os.path.basename(img_f))[0] + "." + conversion_format
        save_path_2 = os.path.join(save_path, nameImg)

        # Conversione dei PSD
        if file_extension == ".psd":
            try:
                pr.update()
                print(img_f)
                temp_img = PSDImage.open(img_f)
                temp_img2 = temp_img.composite().convert("RGB")  # Unisci livelli e cambia metodo colore
                pr.update()
                temp_img2.save(save_path_2, quality=90)
            # Se non riesce a convertire il psd, utilizza le API di Photoshop
            except:
                if show is False:
                    tk.messagebox.showerror("IMPOSSIBILE APRIRE UNO O PIU FILE",
                                            "Alcuni file PSD non riescono ad esser elaborati.\n\n"
                                            " Se Photoshop è installato, verrà aperto e utilizzato\n"
                                            " per l'elaborazione.")
                    show = True
                with Session(img_f, action="open", auto_close=True) as ps:
                    ps.echo(ps.active_document.name)
                    active_document = ps.active_document
                    print(conversion_format)
                    if "JPG" in conversion_format:
                        options = ps.JPEGSaveOptions(quality=10)
                    elif "PNG" in conversion_format:
                        options = ps.PNGSaveOptions()
                    elif "GIF" in conversion_format:
                        options = ps.GIFSaveOptions()
                    elif "TIFF" in conversion_format:
                        options = ps.TiffSaveOptions()
                    elif "BMP" in conversion_format:
                        options = ps.BMPSaveOptions
                    else:
                        options = ps.JPEGSaveOptions(quality=10)

                    active_document.saveAs(save_path_2, options)
            window.update()
        else:
            # Conversione dei files immagine
            temp_img = Image.open(img_f)
            temp_img2 = temp_img.convert("RGB")
            temp_img2.save(save_path_2)
            pr.update()
            # window.update()
