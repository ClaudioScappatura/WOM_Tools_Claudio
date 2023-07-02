
from photoshop import Session


# descrive il funzionamento del radio button "due immagini"
def multiple_def_function(value_rb):
    if value_rb == 2:
        return "Puoi selezionare una o molteplici immagini. \n La struttura del file " \
               ".psd\n diventerà così per ogni immagine:\n" \
               " > Traduzione (Gruppo)\n" \
               " > Pulizia    (Gruppo)\n" \
               "  > Immagine  (Bloccata)"
    else:
        return "  Nel finder dovrai selezionare " \
               "2 immagini. \n La struttura del file " \
               ".psd sarà del tipo:\n" \
               " > Traduzione (Gruppo)\n" \
               " > Pulizia    (Gruppo)\n" \
               "      > Immagine2  (SmartObject)\n" \
               "   > Immagine1  (Bloccata)"


def psd_image_save(work_lab, p_step, progress, radio_value, image_paths, image_paths_2, path_save):
    count = 0
    work_lab.configure(text="Apertura di Photoshop...")
    progress.set(0.01)
    progress.update()
    # selezionate più immagini
    if radio_value == 2:
        # Apri una per volta tutte le immagini selezionate
        for img_p in image_paths:
            count += 1
            # Apri in Photoshop
            with Session(img_p, action="open") as ps:
                work_lab.configure(text="Photoshop sta elaborando...")
                progress.set(count*p_step)
                progress.update()
                ps.echo(ps.active_document.name)
                active_document = ps.active_document

                # Crea nuovi gruppi
                group_layer1 = active_document.layerSets.add()
                group_layer1.name = "Pulizia"

                group_layer2 = active_document.layerSets.add()
                group_layer2.name = "Traduzione"

                output_path = path_save + "\\"
                output_path += active_document.name
                options = ps.PhotoshopSaveOptions()
                layers = active_document.artLayers

                # Salvataggio PSD
                active_document.saveAs(output_path, options, True)
                active_document.close()

    # Selezionate due immagini
    else:
        work_lab.configure(text="Photoshop sta elaborando...")
        # Open prima img
        with Session(image_paths, action="open") as ps:
            progress.set(1)
            ps.echo(ps.active_document.name)
            active_document = ps.active_document

            # Apre ed inserisce la seconda immagine
            desc = ps.ActionDescriptor
            desc.putPath(ps.app.charIDToTypeID("null"), image_paths_2)
            event_id = ps.app.charIDToTypeID("Plc ")  # `Plc` need one space in here.
            ps.app.executeAction(ps.app.charIDToTypeID("Plc "), desc)

            # Crea nuovi gruppi
            group_layer1 = active_document.layerSets.add()
            group_layer1.name = "Pulizia"

            group_layer2 = active_document.layerSets.add()
            group_layer2.name = "Traduzione"

            output_path = path_save + "\\"
            output_path += active_document.name
            options = ps.PhotoshopSaveOptions()
            layers = active_document.artLayers
            progress.update()
            # Salvataggio PSD
            active_document.saveAs(output_path, options, True)
            active_document.close()

