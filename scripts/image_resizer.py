#!/usr/bin/env python3
"""
Interactive Image Resizer
Allows you to select an image from the project, view its properties,
and resize it proportionally.
"""

import os
from pathlib import Path
from PIL import Image
import sys


# Supported image formats
SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.tif'}


def find_images(directory):
    """Recursively find all image files in the directory."""
    images = []
    directory_path = Path(directory)
    
    for ext in SUPPORTED_FORMATS:
        images.extend(directory_path.rglob(f'*{ext}'))
        images.extend(directory_path.rglob(f'*{ext.upper()}'))
    
    return sorted(images)


def format_file_size(size_bytes):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def display_image_info(image_path):
    """Display image information."""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            file_size = os.path.getsize(image_path)
            
            print("\n" + "="*60)
            print(f"Image: {image_path}")
            print(f"Dimensions: {width} x {height} pixels")
            print(f"File Size: {format_file_size(file_size)}")
            print(f"Format: {img.format}")
            print(f"Mode: {img.mode}")
            print("="*60 + "\n")
            
            return width, height, file_size
    except Exception as e:
        print(f"Error reading image: {e}")
        return None, None, None


def resize_image_proportionally(image_path, target_width=None, target_height=None, scale_factor=None):
    """Resize image proportionally based on target width, height, or scale factor."""
    try:
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            
            if scale_factor:
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
            elif target_width:
                scale = target_width / original_width
                new_width = target_width
                new_height = int(original_height * scale)
            elif target_height:
                scale = target_height / original_height
                new_width = int(original_width * scale)
                new_height = target_height
            else:
                print("Error: No resize parameter provided")
                return False
            
            print(f"\nResizing from {original_width}x{original_height} to {new_width}x{new_height}")
            
            # Resize with high-quality resampling
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Ask for output filename
            original_path = Path(image_path)
            default_name = f"{original_path.stem}_resized{original_path.suffix}"
            output_name = input(f"Enter output filename (default: {default_name}): ").strip()
            
            if not output_name:
                output_name = default_name
            
            output_path = original_path.parent / output_name
            
            # Handle overwrite confirmation
            if output_path.exists():
                confirm = input(f"File {output_path} already exists. Overwrite? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("Operation cancelled.")
                    return False
            
            # Save the resized image
            resized_img.save(output_path, quality=95, optimize=True)
            
            new_size = os.path.getsize(output_path)
            print(f"\n✓ Image saved to: {output_path}")
            print(f"  New dimensions: {new_width} x {new_height} pixels")
            print(f"  New file size: {format_file_size(new_size)}")
            
            return True
            
    except Exception as e:
        print(f"Error resizing image: {e}")
        return False


def handle_image_resize_menu(image_path):
    """Handle the resize menu for a specific image."""
    width, height, file_size = display_image_info(image_path)
    
    if width is None:
        return False
    
    # Resize options
    while True:
        print("\nResize Options:")
        print("1. Resize by scale factor (e.g., 0.5 for 50%, 2.0 for 200%)")
        print("2. Resize by target width (maintains aspect ratio)")
        print("3. Resize by target height (maintains aspect ratio)")
        print("4. Exit")
        
        resize_choice = input("\nChoose an option (1-4): ").strip()
        
        if resize_choice == '1':
            try:
                scale = float(input("Enter scale factor (e.g., 0.5, 1.5, 2.0): ").strip())
                if scale <= 0:
                    print("Scale factor must be positive.")
                    continue
                resize_image_proportionally(image_path, scale_factor=scale)
            except ValueError:
                print("Invalid scale factor. Please enter a number.")
        
        elif resize_choice == '2':
            try:
                target_w = int(input(f"Enter target width (current: {width}): ").strip())
                if target_w <= 0:
                    print("Width must be positive.")
                    continue
                resize_image_proportionally(image_path, target_width=target_w)
            except ValueError:
                print("Invalid width. Please enter a number.")
        
        elif resize_choice == '3':
            try:
                target_h = int(input(f"Enter target height (current: {height}): ").strip())
                if target_h <= 0:
                    print("Height must be positive.")
                    continue
                resize_image_proportionally(image_path, target_height=target_h)
            except ValueError:
                print("Invalid height. Please enter a number.")
        
        elif resize_choice == '4':
            return True
        
        else:
            print("Invalid option. Please try again.")


def main():
    """Main interactive function."""
    # Get the project root directory (parent of scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Check if image path is provided as command-line argument
    if len(sys.argv) > 1:
        image_path_arg = sys.argv[1]
        image_path = Path(image_path_arg)
        
        # Handle both absolute and relative paths
        if not image_path.is_absolute():
            # Try relative to current directory first
            if not image_path.exists():
                # Try relative to project root
                image_path = project_root / image_path
            else:
                image_path = Path(image_path_arg).resolve()
        else:
            image_path = Path(image_path_arg)
        
        # Validate the image file
        if not image_path.exists():
            print(f"Error: Image file not found: {image_path}")
            print(f"Please check the path and try again.")
            sys.exit(1)
        
        if image_path.suffix.lower() not in SUPPORTED_FORMATS:
            print(f"Error: Unsupported image format: {image_path.suffix}")
            print(f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}")
            sys.exit(1)
        
        # Direct mode: process the specified image
        print("="*60)
        print("Interactive Image Resizer")
        print("="*60)
        print(f"Processing image: {image_path}")
        
        try:
            handle_image_resize_menu(image_path)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Goodbye!")
        except Exception as e:
            print(f"An error occurred: {e}")
            sys.exit(1)
        
        return
    
    # Interactive mode: show menu to select image
    print("="*60)
    print("Interactive Image Resizer")
    print("="*60)
    print(f"Scanning images in: {project_root}")
    
    # Find all images
    images = find_images(project_root)
    
    if not images:
        print("No supported image files found in the project.")
        return
    
    print(f"\nFound {len(images)} image(s)\n")
    
    while True:
        # Display image list
        print("\n" + "-"*60)
        print("Available Images:")
        print("-"*60)
        for idx, img_path in enumerate(images, 1):
            rel_path = img_path.relative_to(project_root)
            print(f"{idx:3d}. {rel_path}")
        
        print(f"\n{len(images) + 1:3d}. Exit")
        print("-"*60)
        
        # Get user selection
        try:
            choice = input(f"\nSelect an image (1-{len(images) + 1}): ").strip()
            
            if not choice:
                continue
            
            choice_num = int(choice)
            
            if choice_num == len(images) + 1:
                print("Goodbye!")
                break
            
            if choice_num < 1 or choice_num > len(images):
                print("Invalid selection. Please try again.")
                continue
            
            selected_image = images[choice_num - 1]
            
            # Handle resize menu
            handle_image_resize_menu(selected_image)
        
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
