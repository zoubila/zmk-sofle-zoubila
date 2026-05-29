# nice_view_custom

Local nice!view shield based on the upstream ZMK `nice_view` shield.

Put one or more `.png` files in `images/`. During the ZMK build, `scripts/generate_art.py`
converts every PNG into a 1-bit LVGL image and the peripheral half chooses one at random
on boot.

Notes:

- Target display size is 160x68.
- Portrait images are rotated clockwise automatically.
- Images are resized with center-crop and nearest-neighbor sampling.
- Transparent pixels are composited on white before conversion.

## Image preparation

For best results, do not dither a large photo and then resize it in the firmware build. Resize and
crop the image first, then dither it at the final pixel size.

Recommended source size for a portrait image on this keyboard:

- `68x160` before adding it to `images/`

Recommended Ditherlicious workflow:

- Crop tightly around the subject before uploading.
- Resize to `68x160` before uploading; Ditherlicious does not resize the image.
- Use `Luminosity` as the default black and white conversion.
- Increase exposure until the subject is mostly readable on a light background.
- Keep contrast moderate; excessive contrast creates large black areas.
- Aim for roughly 35-55% black pixels at the final size.
