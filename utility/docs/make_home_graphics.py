"""
Generate the home-page images in docs/images, in the charcoal-and-cyan style of the Alpaca v2 logo card:

  abp-hero.jpg      banner: an astrophoto with the Alpaca logo, wordmark and a photo of the Polaris
  abp-gallery.jpg   a grid of images captured with the Polaris, captioned with lens and sub-exposure length
  abp-satellites.jpg  the satellite imaging examples, captioned the same way

The feature icons are hand-editable SVGs in docs/images/icons/, laid out as an HTML table in docs/index.md.

The source photos are not in the repo. Pass the folder that holds them (see SOURCES below) and a folder
of fonts containing Franklin Gothic Demi (FRADM.TTF) and Segoe UI (segoeui.ttf), e.g. C:\\Windows\\Fonts.

Usage (from the repo root):
    uv run --no-project --with pillow python utility/docs/make_home_graphics.py \\
        <sources dir> /mnt/c/Windows/Fonts docs/images
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

Image.MAX_IMAGE_PIXELS = None

CHARCOAL = (46, 45, 50)
CYAN = '#1ec8ff'
WHITE = (255, 255, 255)
GREY = (176, 180, 190)

HERO_BACKGROUND = 'C92 Carina Nebula GLAT001S_GLON288_SHO_400mm_20s_780s_spcc_bx_nx_ss_nn_vsc_final.jpg'
POLARIS = 'abp-v2-motor-limits-bare.png'
LOGO = 'abp-logo-hires.png'

# (file, title, caption) -- every image was captured with a Benro Polaris and the Alpaca driver.
# FF equiv. focal length: x3.4 for the MiniCam8 (IMX585) used for SHO/HSO/LRGB images, x1 for the full-frame R5.
GALLERY = [
    ('C92 Carina Nebula GLAT001S_GLON288_SHO_400mm_20s_780s_spcc_bx_nx_ss_nn_vsc_final.jpg', 'Carina Nebula', '400 mm (1360 mm FF equiv.) · 39 × 20 s'),
    ('IC 434 Horsehead HSO_400mm_120s_5760s_composed_dn-1000.jpg', 'Horsehead Nebula', '400 mm (1360 mm FF equiv.) · 48 × 120 s'),
    ('M16 Eagle Nebula GLAT000N_GLON020_SHO_300mm_F2.8_15s_5820s_spcc_bx_nx_final.jpg', 'Eagle Nebula', '300 mm (1020 mm FF equiv.) · 388 × 15 s'),
    ('M8 Lagoon Nebula GLAT000N_GLON010_SHO_200mm_F2.8_60s_2100s_spcc_bx_nx_final.jpg', 'Lagoon Nebula', '200 mm (680 mm FF equiv.) · 35 × 60 s'),
    ('NGC_6334_Cats_Paw_EF400_15s_Result__HSO_13395s_spcc_curves_recomp.jpg', "Cat's Paw Nebula", '400 mm (1360 mm FF equiv.) · 893 × 15 s'),
    ('NGC 2070 Tarantula GLAT030S_GLON280_SHO_200mm_F2.8_60s_3840s_spcc_bx_nx_final.jpg', 'Tarantula Nebula', '200 mm (680 mm FF equiv.) · 64 × 60 s'),
    ('C77 Centaurus A GLAT020N_GLON310_LRGB_300mm_x2_15s_3645s_spcc_bx_nx_final.jpg', 'Centaurus A', '300 mm + 2× (2040 mm FF equiv.) · 243 × 15 s'),
    ('C80_Omega_Centauri_EF400_2s_Result__LRGB_2442s_cc_nr_str_abr.jpg', 'Omega Centauri', '400 mm (1360 mm FF equiv.) · 1221 × 2 s'),
    ('C33 East Veil Nebula GLAT010S_GLON080_HSO_200mm_F2.8_120s_2640s_spcc_bx_nx_final.jpg', 'Eastern Veil Nebula', '200 mm (680 mm FF equiv.) · 22 × 120 s'),
]
PANORAMA = ('[Group 0]-GLAT000S_GLON344_1_LRGB_stretched_result_GLAT022N_GLON352_2_LRGB_stretched_result-34 images.png',
            'Milky Way mosaic', '32 mm (109 mm FF equiv.) · 16 × 3 panels')

# (file, title, caption) for the Satellite Imaging guide
SATELLITES = [
    ('Spin_at_NGC6134_Little_Pincushion.jpg', 'Spin around NGC 6134', 'Mount rotated during a sequence of exposures'),
    ('Starlink Satellite B 2026-10-20_20-34-23_L_-10.00_2.00s_1471.jpg', 'Starlink Satellite', 'Tracked by the Alpaca Driver · 2 s exposure'),
]


def font(fonts: Path, name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(fonts / name), size)


def cover(im: Image.Image, w: int, h: int, focus=(0.5, 0.5)) -> Image.Image:
    """Scale and crop to exactly w x h, keeping the focus point (fractions of width, height) in view."""
    scale = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    x = min(max(0, round(im.width * focus[0] - w / 2)), im.width - w)
    y = min(max(0, round(im.height * focus[1] - h / 2)), im.height - h)
    return im.crop((x, y, x + w, y + h))


def horizontal_fade(w: int, h: int, start: float, end: float, alpha: int) -> Image.Image:
    """Mask that is `alpha` left of `start` and fades to 0 at `end` (fractions of width)."""
    row = [alpha if x < start * w else max(0, round(alpha * (end * w - x) / ((end - start) * w))) for x in range(w)]
    return Image.frombytes('L', (w, 1), bytes(row)).resize((w, h))


def hero(src: Path, fonts: Path) -> Image.Image:
    w, h = 1600, 600
    bg = cover(Image.open(src / HERO_BACKGROUND).convert('RGB'), w, h, (0.6, 0.5))
    bg = Image.blend(bg, Image.new('RGB', (w, h), (0, 0, 0)), 0.25)
    bg.paste(Image.new('RGB', (w, h), CHARCOAL), (0, 0), horizontal_fade(w, h, 0.36, 0.66, 255))

    # soft light behind the Polaris so its dark body reads against the sky
    glow = Image.new('L', (w, h), 0)
    ImageDraw.Draw(glow).ellipse((1080, 90, 1500, 510), fill=70)
    bg.paste(Image.new('RGB', (w, h), (190, 215, 235)), (0, 0), glow.filter(ImageFilter.GaussianBlur(70)))

    polaris = Image.open(src / POLARIS).convert('RGBA')
    polaris = polaris.crop(polaris.getbbox())
    polaris = polaris.resize((470, round(470 * polaris.height / polaris.width)), Image.LANCZOS)
    polaris.putalpha(polaris.getchannel('A').point(lambda a: 0 if a < 40 else a))  # resampling leaves a faint box of near-zero alpha
    shadow = Image.new('L', (polaris.width + 80, polaris.height + 80), 0)  # padded so the blur isn't clipped
    shadow.paste(polaris.getchannel('A').point(lambda a: a * 0.6), (40, 40))
    bg.paste((0, 0, 0), (1062 - 40, 92 - 40), shadow.filter(ImageFilter.GaussianBlur(14)))
    bg.paste(polaris, (1050, 70), polaris)

    logo = Image.open(src / LOGO).convert('RGBA')
    logo = logo.crop(logo.getbbox())
    logo = logo.resize((round(logo.width * 250 / logo.height), 250), Image.LANCZOS)
    glow = logo.getchannel('A').filter(ImageFilter.GaussianBlur(6)).point(lambda a: a * 0.6)
    bg.paste((30, 200, 255), (80, 110), glow)
    bg.paste(logo, (80, 110), logo)

    d = ImageDraw.Draw(bg)
    x = 80 + logo.width + 50
    d.text((x, 150), 'Alpaca', font=font(fonts, 'FRADM.TTF', 112), fill=WHITE)
    d.text((x + 4, 282), 'Benro Polaris', font=font(fonts, 'segoeui.ttf', 54), fill=CYAN)
    d.text((82, 420), 'ASCOM Alpaca driver and Pilot app for the Benro Polaris', font=font(fonts, 'segoeui.ttf', 30), fill=WHITE)
    d.text((82, 464), 'Slewing  ·  Rotating  ·  Targeting  ·  Tracking  ·  Guiding  ·  Jogging', font=font(fonts, 'segoeui.ttf', 26), fill=GREY)
    return bg


def caption(tile: Image.Image, title: str, sub: str, fonts: Path) -> Image.Image:
    """Shade the bottom of a tile and write a title and caption on it."""
    shade = Image.new('L', (1, tile.height))
    shade.putdata([max(0, round(200 * (y - tile.height * 0.62) / (tile.height * 0.38))) for y in range(tile.height)])
    tile.paste((0, 0, 0), (0, 0), shade.resize(tile.size))
    d = ImageDraw.Draw(tile)
    d.text((22, tile.height - 50), title, font=font(fonts, 'FRADM.TTF', 30), fill=WHITE, anchor='ls')
    d.text((22, tile.height - 20), sub, font=font(fonts, 'segoeui.ttf', 22), fill=GREY, anchor='ls')
    return tile


def gallery(src: Path, fonts: Path) -> Image.Image:
    cols, tw, th, gap = 3, 640, 400, 10
    rows = -(-len(GALLERY) // cols)
    pano_h = 420
    w = cols * tw + (cols - 1) * gap
    h = rows * (th + gap) + pano_h
    im = Image.new('RGB', (w, h), CHARCOAL)
    for i, (name, title, sub) in enumerate(GALLERY):
        tile = cover(Image.open(src / name).convert('RGB'), tw, th)
        im.paste(caption(tile, title, sub, fonts), ((i % cols) * (tw + gap), (i // cols) * (th + gap)))
    name, title, sub = PANORAMA
    im.paste(caption(cover(Image.open(src / name).convert('RGB'), w, pano_h, (0.5, 0.55)), title, sub, fonts), (0, rows * (th + gap)))
    return im


def satellites(src: Path, fonts: Path) -> Image.Image:
    tw, th, gap = 960, 540, 10
    im = Image.new('RGB', (len(SATELLITES) * (tw + gap) - gap, th), CHARCOAL)
    for i, (name, title, sub) in enumerate(SATELLITES):
        tile = cover(Image.open(src / name).convert('RGB'), tw, th)
        im.paste(caption(tile, title, sub, fonts), (i * (tw + gap), 0))
    return im


def main() -> None:
    src, fonts, out = (Path(a) for a in sys.argv[1:4])
    hero(src, fonts).save(out / 'abp-hero.jpg', quality=88, optimize=True, progressive=True)
    gallery(src, fonts).save(out / 'abp-gallery.jpg', quality=85, optimize=True, progressive=True)
    satellites(src, fonts).save(out / 'abp-satellites.jpg', quality=85, optimize=True, progressive=True)


if __name__ == '__main__':
    main()
