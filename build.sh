#!/bin/bash

# Build script for static assets repository
# This script processes source files from src/ and outputs optimized files to dist/

# Exit on error, but allow find to return empty results
set -e

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p dist/css
mkdir -p dist/js
mkdir -p dist/images
mkdir -p dist/data
mkdir -p dist/md

# Copy CNAME file if it exists
if [ -f src/CNAME ]; then
    cp src/CNAME dist/CNAME
    echo "CNAME file copied."
fi

# Copy all images to dist/images while preserving folder structure
if [ -d src/images ] && [ "$(ls -A src/images 2>/dev/null)" ]; then
    echo "Copying images to dist/images..."
    rsync -a src/images/ dist/images/
    echo "Images copied successfully."
else
    echo "No images directory or images found, skipping..."
fi

# Copy data files to dist/data while preserving folder structure
if [ -d src/data ] && [ "$(ls -A src/data 2>/dev/null)" ]; then
    echo "Copying data to dist/data..."
    rsync -a src/data/ dist/data/
    echo "Data files copied successfully."
else
    echo "No data directory or data files found, skipping..."
fi

# Copy markdown files to dist/md while preserving folder structure
if [ -d src/md ] && [ "$(ls -A src/md 2>/dev/null)" ]; then
    echo "Copying markdown files to dist/md..."
    rsync -a src/md/ dist/md/
    echo "Markdown files copied successfully."
else
    echo "No md directory or markdown files found, skipping..."
fi

# Generate a list of image files to convert to WebP
echo "Generating list of image files to convert to WebP..."
image_files=$(find src/images -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) 2>/dev/null || true)

if [ -n "$image_files" ]; then
    echo "Image files to process:"
    echo "$image_files"
    
    # Convert images to WebP format
    echo "Converting images to WebP format..."
    for file in $image_files; do
        # Get relative path from src/images
        rel_path=$(echo "$file" | sed "s|^src/images/||")
        # Get directory part (empty if file is directly in src/images/)
        rel_dir=$(dirname "$rel_path")
        
        # Build target directory path
        if [ "$rel_dir" = "." ]; then
            target_dir="dist/images"
        else
            target_dir="dist/images/$rel_dir"
        fi
        
        # Create target directory
        mkdir -p "$target_dir"
        
        # Build output filename
        base_name=$(basename "${file%.*}")
        output_file="$target_dir/$base_name.webp"
        
        echo "Processing image: $file -> $output_file"
        
        # Remove previous WebP so a failed run cannot leave a stale file
        rm -f "$output_file"
        
        # Convert to WebP with error checking
        if cwebp "$file" -o "$output_file" 2>&1; then
            echo "  ✓ Successfully created: $output_file"
        else
            echo "  ✗ Failed to convert: $file"
            exit 1
        fi
    done
    echo "WebP conversion completed."
else
    echo "No images found for WebP conversion, skipping..."
fi

# Generate grid preview thumbnails (dist/images/_thumbs/, build output only)
if [ -d dist/images ] && [ "$(ls -A dist/images 2>/dev/null)" ]; then
    echo "Generating preview thumbnails..."
    python3 scripts/generate_thumbs.py
fi

# Generate a list of CSS files to minify
echo "Generating list of CSS files to minify..."
css_files=$(find src/css -type f -name "*.css" 2>/dev/null || true)

if [ -n "$css_files" ]; then
    echo "CSS files to process:"
    echo "$css_files"
    
    # Minify CSS files
    echo "Minifying CSS files..."
    for file in $css_files; do
        echo "Input CSS file: $file"
        target_dir="dist/css/$(dirname "$file" | sed "s|^src\/css||")"
        mkdir -p "$target_dir"
        output_file="$target_dir$(basename "${file%.css}.min.css")"
        echo "Target directory: $target_dir"
        echo "Output CSS file: $output_file"
        csso "$file" -o "$output_file"
    done
    echo "CSS minification completed."
else
    echo "No CSS files found, skipping minification..."
fi

# Generate a list of JS files to minify
echo "Generating list of JS files to minify..."
js_files=$(find src/js -type f -name "*.js" 2>/dev/null || true)

if [ -n "$js_files" ]; then
    echo "JS files to process:"
    echo "$js_files"
    
    # Minify JS files
    echo "Minifying JS files..."
    for file in $js_files; do
        echo "Input JS file: $file"
        target_dir="dist/js/$(dirname "$file" | sed "s|^src\/js||")"
        mkdir -p "$target_dir"
        output_file="$target_dir$(basename "${file%.js}.min.js")"
        echo "Target directory: $target_dir"
        echo "Output JS file: $output_file"
        uglifyjs "$file" -o "$output_file"
    done
    echo "JS minification completed."
else
    echo "No JS files found, skipping minification..."
fi

# Copy static asset browser site to dist root
if [ -d src/site ] && [ "$(ls -A src/site 2>/dev/null)" ]; then
    echo "Copying site files to dist/..."
    rsync -a src/site/ dist/
    echo "Site files copied successfully."
fi

echo "Build process completed."
