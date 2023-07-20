import numpy as np
from photoshop import Session
import photoshop.api as ps
from spellchecker import SpellChecker
import nltk


def correggi_testo(testo):
    spell = SpellChecker()
    frasi = nltk.sent_tokenize(testo)
    testo_corretto = ""

    for frase in frasi:
        parole = nltk.word_tokenize(frase)
        parole_corrette = [spell.correction(parola) for parola in parole]
        frase_corretta = ' '.join(parole_corrette)
        testo_corretto += frase_corretta + " "

    return testo_corretto


def get_center(box):
    """Calcola il centro di un box."""
    x1, y1, x2, y2 = box[:4]
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2])


def get_size(box):
    """Calcola la dimensione di un box."""
    x1, y1, x2, y2 = box[:4]
    return np.linalg.norm(np.array([x2 - x1, y2 - y1]))


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
                    x1, y1, x2, y2, text, text_dim = box
                    nx1, ny1, nx2, ny2, new_text, new_text_dim = new_box
                    try:
                        text = correggi_testo(text)
                        new_text = correggi_testo(new_text)
                    except Exception as e:
                        print(f"Eccezione nel type del testo {text} oppure {new_text}: {e}")
                    new_boxes[i] = [min(x1, nx1), min(y1, ny1), max(x2, nx2), max(y2, ny2), f"{new_text}\n{text}", (text_dim + new_text_dim) / 2]
                    # new_boxes[i] = [min(x1, nx1), min(y1, ny1), max(x2, nx2), max(y2, ny2), f"{new_text} {text}", (text_dim + new_text_dim) / 2]
                    break
            else:
                new_boxes.append(box)
        if len(new_boxes) == len(merged_boxes):
            # Se non ci sono più box da unire, esci dal ciclo
            break
        merged_boxes = new_boxes
    return merged_boxes


def print_fonts():
    img_list = []
    img_list.append(r"C:\Users\claud\Downloads\74 Tradotto\2.psd")
    for img in img_list:
        with Session(img, action='open', auto_close=False) as app:
            doc = app.active_document
            for layer in doc.layers:
                if layer.kind == 2:  # Controlla se il layer è un layer di testo
                    font_name = layer.textItem.font  # Ottiene il nome del font
                    print(f"Layer {layer.name} utilizza il font {font_name}")
            exit(1)


def type_boxes(doc, result, watermarks):
    word_boxes = []
    for res1 in result:
        for box in res1:
            if not any(item in box[1][0].lower() for item in watermarks):
                x1, y1, x2, y2, text = int(box[0][0][0]), int(box[0][0][1]), int(box[0][2][0]), int(box[0][2][1]), box[1][0]
                # La dimensione del font corrisponde all'altezza del testo
                text_dim = (y2 - y1)
                word_boxes.append([x1, y1, x2, y2, text, text_dim])

    # Merge dei box vicini
    merged_result = merge_boxes(word_boxes, 0.65)
    app = ps.Application()

    app.currentTool = 'moveTool'
    doc_resolution = (72 / doc.resolution)
    # In RGB
    app.DoAction('beRGB', 'AutoCleaner')
    # Colore nero
    text_color = ps.SolidColor()
    text_color.rgb.red = 0
    text_color.rgb.green = 0
    text_color.rgb.blue = 0

    for count, mr in enumerate(merged_result):
        if len(mr[4]) > 4:
            new_text_layer = doc.artLayers.add()
            new_text_layer.kind = ps.LayerKind.TextLayer
            new_text_layer.name = ' '.join(mr[4].replace('\n', ' ').split())

            textItem = new_text_layer.textItem
            textItem.kind = ps.TextType.ParagraphText
            textItem.color = text_color
            # textItem.font = 'AnimeAce2.0BB'
            textItem.font = 'CCWildWordsLower-Regular'
            textItem.hyphenation = True
            stretch = ((mr[2] - mr[0]) * 0.18) / 2
            textItem.size = (mr[5] * doc_resolution) * 0.93
            textItem.justification = ps.Justification.Center

            textItem.position = [mr[0] - stretch, mr[1]]
            textItem.width = ((mr[2] - mr[0]) * doc_resolution) + stretch
            textItem.height = ((mr[3] - mr[1]) * doc_resolution) + stretch
            textItem.contents = mr[4]
            # textItem.contents = textItem.contents.replace("\n", "")
            print(f"Type effettuato -> {mr}")
