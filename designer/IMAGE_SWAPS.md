# Image Swap Feature (Quick Update)

The Image Swap feature allows designers to quickly swap out faction images in the live build without rebuilding the entire application.

## How It Works

1. **Designer Interface** (Simple Update section):
   - Add rows with format: `<acronym>-<filename>.webp` (e.g., "fm-glyph.webp")
   - Upload replacement images for each filename
   - Deploy individual swaps with a single click

2. **Server Processing** (designer_server.py):
   - Images are stored in the designer's `data/factions/<fid>/imageSwaps/` directory
   - Each swap is logged as a completed request for audit trail
   - Filename format is validated: must match `acr-name.webp` pattern

3. **Build Deployment**:
   - During deployment, the `apply-image-swaps.py` script copies swapped images to the build's `webp/images/` folder
   - Images replace their counterparts in the live build
   - The deploy-homebrew-to-vm.sh script can be modified to call this during `--assets` sync

## File Locations

- **Designer UI**: `/www/app.js` - renderSimpleUpdateImageSwaps() function
- **Server Handler**: `/server/designer_server.py` - handle_image_swap_push() function
- **Deploy Helper**: `/server/apply-image-swaps.py` - Copies swaps to build

## Usage

### For Designers

1. Navigate to Faction → Simple Update
2. Scroll to "Quick Image Swap" section
3. Click "+ Add image swap row"
4. Enter filename (e.g., "fm-glyph.webp")
5. Click "Upload" to add replacement image
6. Click "Deploy" to push to build
7. The image will be swapped in the live build immediately

### For Deployment

```bash
# Apply image swaps for a faction before redeploying assets
python3 /path/to/designer/server/apply-image-swaps.py <faction-id> /path/to/homebrew/build

# Or during normal asset deployment (if integrated)
./deploy-homebrew-to-vm.sh --assets
```

## Validation

- Filenames must match pattern: `[a-z0-9]{2,3}-[a-z0-9\-]+\.webp` (case-insensitive)
- Images must be valid webp, png, or jpg files
- Source images are validated against magic bytes before storage

## Limitations

- Only supports images in the `webp/images/` folder
- Filename format is strict to prevent path traversal attacks
- Each swap is independent (no batch operations yet)

## Testing

Run the test suite:

```bash
npm test -- designer/dev/test-image-swap.js
```

Or manually:

1. Start the designer server and frontend
2. Create a test faction and build it
3. Navigate to Simple Update
4. Add an image swap row with test data
5. Verify the UI responds correctly

## Future Enhancements

- Batch image swap uploads
- Image preview thumbnails
- Automatic filename detection from build
- Integration with deploy scripts
