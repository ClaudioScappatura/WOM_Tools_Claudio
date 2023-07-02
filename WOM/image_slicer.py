from PIL import Image


def merge_images_vertically(img1: Image.Image, img2: Image.Image) -> Image.Image:
    merged = Image.new('RGB', (max(img1.width, img2.width), img1.height + img2.height))
    merged.load()
    merged.paste(img1, (0, 0))
    merged.paste(img2, (0, img1.height))
    return merged


def expand_image_vertically(image: Image.Image, expansions: list[Image.Image],
                            skipper: int, length: int) -> list[Image.Image, int]:
    out: Image.Image = image
    inc: int = 0

    for _, x in enumerate(expansions[skipper:]):
        if out.height <= length:
            out = merge_images_vertically(out, x)
            inc += 1
        else:
            break

    return [out, skipper + inc]


def find_cut_height(img: Image.Image,
                    desired_height: int | None = 10000,
                    min_height: int | None = 1,
                    max_height: int | None = 10000,
                    tolerance: int | None = 5) -> int:
    l_img = img.load()
    for posy in reversed(range(min(desired_height + 1, img.height))):
        # noinspection PyUnresolvedReferences
        sample = l_img[0, posy]
        for posx in range(img.width):
            # noinspection PyUnresolvedReferences
            if not (sample[0] - tolerance <= l_img[posx, posy][0] <= sample[0] + tolerance):  # red
                break
            # noinspection PyUnresolvedReferences
            if not (sample[1] - tolerance <= l_img[posx, posy][1] <= sample[1] + tolerance):  # green
                break
            # noinspection PyUnresolvedReferences
            if not (sample[2] - tolerance <= l_img[posx, posy][2] <= sample[2] + tolerance):  # blue
                break

            if min_height >= posy:
                return desired_height

            if posx == img.width - 1:
                return posy
    return desired_height


# todo aggiornare la p anche nelle altre funz
def image_slicer(p_incr,p, window, images: list[Image.Image],
                 desired_height: int | None = 10000,
                 min_height: int | None = 1000,
                 max_height: int | None = 10000) -> list[Image.Image]:
    min_height = min(min_height, desired_height, max_height)
    max_height = max(min_height, desired_height, max_height)

    if len(images) <= 0:
        return [Image.new("RGB", (0, 0))]

    out = []

    tmp_img = Image.new("RGB", (images[0].width, 0))

    skipper = 0
    for pos, _ in enumerate(images):
        p.set(pos * p_incr)
        p.update()
        if pos < skipper:
            p.set(pos * p_incr + p_incr)
            p.update()
            continue

        if tmp_img.height <= desired_height:
            tmp_img, skipper = expand_image_vertically(tmp_img, images, pos, desired_height)

        while tmp_img.height > desired_height:
            cut_height = find_cut_height(tmp_img, desired_height, min_height, max_height)
            window.update()
            cropped_img = tmp_img.crop(box=(0, 0, tmp_img.width, cut_height))
            out.append(cropped_img)

            tmp_img = tmp_img.crop(box=(0, cut_height, tmp_img.width, tmp_img.height))

        p.set(pos * p_incr + p_incr)
        p.update()

    if tmp_img.height != 0:
        out.append(tmp_img)

    # tk.messagebox.showinfo("TAGLIO RIUSCITO", ("Progr: " + str(p['value']) + str(p['maximum'])))
    return out
