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
