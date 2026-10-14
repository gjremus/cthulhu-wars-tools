# Quick Start: Image Swap Feature

## Overview

The **Image Swap** feature (part of "Simple Update") allows you to quickly swap faction images without rebuilding the entire application. This is useful for fixing artwork, testing variations, or rapidly iterating on visual assets.

## Step-by-Step Guide

### 1. Navigate to Simple Update

- Open your faction in the designer
- Click the **Simple Update** button (appears after build completes)

### 2. Find the Quick Image Swap Section

Scroll down past the "Fixed Numbers" table to find the **Quick Image Swap** section with:
- Description: "Add image files to swap out in the build"
- Format hint: "acronym-filename.webp (e.g., fm-glyph.webp)"
- An empty table with headers: Filename, Image Preview, Action

### 3. Add an Image Swap Row

- Click **+ Add image swap row** button
- A new row appears in the table

### 4. Enter the Filename

- Type the filename in the format: `<acr>-<name>.webp`
  - Example: `fm-glyph.webp` (Great Cthulhu glyph)
  - Example: `dgt-acolyte.webp` (Dread Curse acolyte)
  - The acronym should match your faction
- The filename must end with `.webp`

### 5. Upload the Replacement Image

- Click **Upload** button in the Action column
- Select your new image file (.webp, .png, or .jpg supported)
- A thumbnail preview appears
- Multiple swaps can use different image formats; they're converted as needed

### 6. Deploy the Swap

- Click **Deploy** button to push to the build
- Status message appears: "Image swap deployed: [filename]"
- The image is immediately available in the live build

### 7. Verify in Build

- Open the build at `https://cwo.freeddns.org/HB/` (or your custom build URL)
- The swapped image should appear in place of the original
- Changes apply to new games; games in progress keep the original

## Important Notes

**Filename Format**
- Must be: `[2-3 letter acronym]-[name].webp`
- Case-insensitive but `.webp` extension required
- Examples: `FM-Glyph.webp`, `dgt-acolyte.webp`, `bb-ancient-one.webp`

**Image Specifications**
- Supported formats: webp, png, jpg
- Recommended: webp for best compression
- Size: should match the original image dimensions
- Quality: ensure adequate contrast for game visibility

**Limitations**
- Only works with built factions
- Image must be for a file that exists in the build's `webp/images/` folder
- Each swap is independent (no batch operations)
- Does not survive a full rebuild (reapply after rebuilding)

## Troubleshooting

**"Invalid filename" error**
- Check format: must be `acr-name.webp`
- Verify acronym is 2-3 letters
- Ensure `.webp` extension

**"Source image not found" error**
- Make sure you uploaded an image
- Check that the file is a valid image format

**Swap doesn't appear in build**
- Verify filename matches an existing asset in the build
- Try refreshing the build page (Cmd+Shift+R on Mac)
- Check browser cache isn't serving old version

## Advanced: Batch Swaps

To swap multiple images at once:

1. Add a row for each swap
2. Enter filenames and upload images for all
3. Click Deploy on each row
4. All swaps apply to the build immediately

## Advanced: Integration with Deployment

When integrating image swaps with your deployment pipeline:

```bash
# Before deploying assets, apply any pending swaps
python3 designer/server/apply-image-swaps.py <faction-id> /path/to/build

# Then deploy normally
./deploy-homebrew-to-vm.sh --assets
```

## Questions?

- Check `designer/IMAGE_SWAPS.md` for technical details
- Review the server code: `designer/server/designer_server.py`
- Check the UI code: `designer/www/app.js` (renderSimpleUpdateImageSwaps)
