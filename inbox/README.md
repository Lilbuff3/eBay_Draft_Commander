# Inbox Test Data

This directory contains test photos for developing and testing the listing creation features.

## Current Folders

### `haeger_vase_demo`
Demo photos for Haeger vase listing test

### `test_job_1`
Generic test job folder

### `yonex`
Yonex product photos (12 photos)

## Usage

These folders are used by the queue manager during development and testing. They are safe to keep for testing purposes, but can be deleted if you need to clean up.

## Cleanup

To remove all test data:

```bash
# Windows
Remove-Item inbox\* -Recurse -Force

# Keep .gitignore
git checkout inbox/.gitignore
```

## Production Note

In production, the `inbox/` folder will be automatically populated with:
- Manually created job folders (photos dropped in)
- Mobile upload folders (created by API: `mobile_YYYYMMDD_HHMMSS_XXXXXX`)

Old job folders should be cleaned up periodically to save disk space.
