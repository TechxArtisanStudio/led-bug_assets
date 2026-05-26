#!/usr/bin/env python3
"""
Script to generate markdown files with asset links for all file types.
This script can scan src/ directory to predict final URLs (default) or scan dist/ 
directory to list actual built files (--dist flag).
Generates separate markdown files for each file type.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Callable, Optional

# Try to import TOML library
try:
    # Python 3.11+ has tomllib built-in
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
except ImportError:
    # Fallback: try tomli package
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

# Default base URL when not in config.toml
DEFAULT_BASE_URL = "https://assets.led-bug.com"

# File type configuration mapping
FILE_TYPE_MAPPING = {
    'webp': {
        'extensions': ['.png', '.jpg', '.jpeg', '.webp'],
        'dist_extensions': ['.webp'],  # In dist/, only .webp files exist (converted from PNG/JPG/JPEG)
        'src_dir': 'src/images',
        'dist_dir': 'dist/images',
        'url_path': 'images',
        'transform': lambda p: p.with_suffix('.webp'),
        'output_file': 'webp.md',
        'description': 'WebP Image Links'
    },
    'svg': {
        'extensions': ['.svg'],
        'src_dir': 'src/images',
        'dist_dir': 'dist/images',
        'url_path': 'images',
        'transform': lambda p: p,  # No transformation
        'output_file': 'svg.md',
        'description': 'SVG Image Links'
    },
    'gif': {
        'extensions': ['.gif'],
        'src_dir': 'src/images',
        'dist_dir': 'dist/images',
        'url_path': 'images',
        'transform': lambda p: p,  # No transformation
        'output_file': 'gif.md',
        'description': 'GIF Image Links'
    },
    'css': {
        'extensions': ['.css'],
        'dist_extensions': ['.min.css'],  # Files in dist/ have .min.css extension
        'src_dir': 'src/css',
        'dist_dir': 'dist/css',
        'url_path': 'css',
        'transform': lambda p: p.with_name(p.stem + '.min.css'),
        'output_file': 'css.md',
        'description': 'CSS File Links'
    },
    'js': {
        'extensions': ['.js'],
        'dist_extensions': ['.min.js'],  # Files in dist/ have .min.js extension
        'src_dir': 'src/js',
        'dist_dir': 'dist/js',
        'url_path': 'js',
        'transform': lambda p: p.with_name(p.stem + '.min.js'),
        'output_file': 'js.md',
        'description': 'JavaScript File Links'
    },
    'data': {
        'extensions': ['.csv', '.json', '.txt', '.xml', '.apk'],
        'src_dir': 'src/data',
        'dist_dir': 'dist/data',
        'url_path': 'data',
        'transform': lambda p: p,  # No transformation
        'output_file': 'data.md',
        'description': 'Data File Links'
    },
    'md': {
        'extensions': ['.md'],
        'src_dir': 'src/md',
        'dist_dir': 'dist/md',
        'url_path': 'md',
        'transform': lambda p: p,  # No transformation
        'output_file': 'md.md',
        'description': 'Markdown File Links'
    }
}


def load_config(project_root: Path) -> Dict:
    """
    Load configuration from config.toml file.
    
    Args:
        project_root: Path to project root directory.
        
    Returns:
        Dictionary containing configuration, or empty dict if not found.
    """
    config_path = project_root / "config.toml"
    
    if not config_path.exists():
        return {}
    
    if tomllib is None:
        return {}
    
    try:
        with open(config_path, 'rb') as f:
            config = tomllib.load(f)
        return config
    except Exception as e:
        print(f"Warning: Could not read config.toml: {e}")
        return {}


def get_base_url_from_config(project_root: Path) -> str:
    """
    Get base URL from config.toml file.
    
    Args:
        project_root: Path to project root directory.
        
    Returns:
        Base URL string, or default placeholder if not found.
    """
    config = load_config(project_root)
    
    if 'repository' in config and 'base_url' in config['repository']:
        return config['repository']['base_url']
    
    # Default fallback for this project
    return DEFAULT_BASE_URL


def find_files_by_type(directory: Path, extensions: List[str], base_dir: Path) -> List[Path]:
    """Find all files with given extensions in directory."""
    files = []
    if not directory.exists():
        return files
    
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            file_path = Path(root) / filename
            if file_path.suffix.lower() in extensions:
                # Get relative path from base directory
                try:
                    rel_path = file_path.relative_to(base_dir)
                    files.append(rel_path)
                except ValueError:
                    # Skip if file is not under base_dir
                    continue
    
    return sorted(files)


def scan_source_directory(project_root: Path, file_type_config: Dict) -> List[Tuple[Path, Path]]:
    """
    Scan src/ directory and predict final URLs based on build transformations.
    Returns list of (source_path, transformed_path) tuples.
    """
    src_dir = project_root / file_type_config['src_dir']
    files = find_files_by_type(src_dir, file_type_config['extensions'], src_dir)
    
    result = []
    transform_func = file_type_config['transform']
    
    for file_path in files:
        # Apply transformation to predict final path
        transformed_path = transform_func(file_path)
        result.append((file_path, transformed_path))
    
    return result


def scan_dist_directory(project_root: Path, file_type_config: Dict) -> List[Tuple[Path, Path]]:
    """
    Scan dist/ directory to list actual built files.
    Returns list of (actual_path, actual_path) tuples (no transformation needed).
    """
    dist_dir = project_root / file_type_config['dist_dir']
    # Use dist_extensions if available, otherwise use regular extensions
    extensions = file_type_config.get('dist_extensions', file_type_config['extensions'])
    files = find_files_by_type(dist_dir, extensions, dist_dir)
    
    result = []
    for file_path in files:
        # In dist mode, use actual file path (no transformation)
        result.append((file_path, file_path))
    
    return result


def generate_markdown_links(
    file_pairs: List[Tuple[Path, Path]],
    url_path: str,
    base_url: str = DEFAULT_BASE_URL
) -> List[str]:
    """Generate markdown links for files."""
    markdown_lines = []
    
    for source_path, final_path in file_pairs:
        # Create the full URL
        full_url = f"{base_url}/{url_path}/{final_path.as_posix()}"
        
        # Create a descriptive name for the link text
        # Remove path separators and file extension, replace with hyphens
        link_name = str(final_path).replace('/', '-').replace('\\', '-')
        # Remove extension
        if final_path.suffix:
            link_name = link_name.replace(final_path.suffix, '')
        
        # Generate markdown link
        markdown_link = f"[{link_name}]({full_url})"
        markdown_lines.append(markdown_link)
    
    return markdown_lines


def write_markdown_file(
    output_path: Path,
    description: str,
    markdown_lines: List[str],
    scan_mode: str,
    source_dir: str
):
    """Write markdown file with links."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# {description}\n\n")
        
        if scan_mode == 'src':
            f.write(f"Generated from source files in `{source_dir}/`\n")
            f.write("These URLs are predicted based on build transformations.\n\n")
        else:
            f.write(f"Generated from built files in `{source_dir}/`\n")
            f.write("These are the actual URLs available after build.\n\n")
        
        if markdown_lines:
            f.write("Copy and paste these links into your markdown files:\n\n")
            for line in markdown_lines:
                f.write(line + "\n\n")
        else:
            f.write("No files found for this type.\n\n")


def process_file_type(
    project_root: Path,
    file_type: str,
    file_type_config: Dict,
    scan_dist: bool,
    base_url: str,
    output_dir: Path
) -> Tuple[int, bool]:
    """
    Process a single file type and generate its markdown file.
    Returns (file_count, success) tuple.
    """
    if scan_dist:
        file_pairs = scan_dist_directory(project_root, file_type_config)
        source_dir = file_type_config['dist_dir']
        scan_mode = 'dist'
    else:
        file_pairs = scan_source_directory(project_root, file_type_config)
        source_dir = file_type_config['src_dir']
        scan_mode = 'src'
    
    if not file_pairs:
        return 0, False
    
    # Generate markdown links
    markdown_lines = generate_markdown_links(
        file_pairs,
        file_type_config['url_path'],
        base_url
    )
    
    # Write to output file
    output_file = output_dir / file_type_config['output_file']
    write_markdown_file(
        output_file,
        file_type_config['description'],
        markdown_lines,
        scan_mode,
        source_dir
    )
    
    return len(file_pairs), True


def main():
    parser = argparse.ArgumentParser(
        description='Generate markdown files with asset links for all file types',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan src/ and predict final URLs (default)
  python scripts/generate_url.py
  
  # Scan dist/ to list actual built files
  python scripts/generate_url.py --dist
  
  # Custom base URL (overrides config.toml)
  python scripts/generate_url.py --base-url https://example.com
  
  # Custom output directory (default is links/)
  python scripts/generate_url.py --output-dir docs/links
        """
    )
    parser.add_argument(
        '--dist',
        action='store_true',
        help='Scan dist/ directory instead of src/ (default: scan src/ and predict URLs)'
    )
    parser.add_argument(
        '--base-url',
        type=str,
        default=None,
        help=f'Base URL for generated links (default: read from config.toml, or {DEFAULT_BASE_URL})'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Directory to write markdown files (default: links/)'
    )
    
    args = parser.parse_args()
    
    # Get the script directory and project root (parent of scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Determine base URL
    if args.base_url:
        base_url = args.base_url
    else:
        base_url = get_base_url_from_config(project_root)
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        # Default to links/ folder in project root
        output_dir = project_root / "links"
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine scan mode
    scan_mode = 'dist' if args.dist else 'src'
    
    print("=" * 60)
    print("Asset Link Generator")
    print("=" * 60)
    print(f"Scan mode: {'dist/ (actual files)' if args.dist else 'src/ (predict URLs)'}")
    print(f"Base URL: {base_url}")
    print(f"Output directory: {output_dir}")
    print("=" * 60)
    print()
    
    # Process each file type
    results = {}
    total_files = 0
    
    for file_type, config in FILE_TYPE_MAPPING.items():
        print(f"Processing {file_type} files...", end=' ', flush=True)
        
        file_count, success = process_file_type(
            project_root,
            file_type,
            config,
            args.dist,
            base_url,
            output_dir
        )
        
        if success:
            print(f"✓ Found {file_count} files")
            results[file_type] = file_count
            total_files += file_count
        else:
            print("✗ No files found")
            results[file_type] = 0
    
    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    for file_type, count in results.items():
        if count > 0:
            output_file = output_dir / FILE_TYPE_MAPPING[file_type]['output_file']
            print(f"  {file_type:10s}: {count:4d} files -> {output_file.name}")
    
    print(f"\nTotal files processed: {total_files}")
    print(f"Output directory: {output_dir}")
    print("=" * 60)
    
    # Show examples
    if total_files > 0:
        print("\nExample links from first file type with files:")
        for file_type, count in results.items():
            if count > 0:
                output_file = output_dir / FILE_TYPE_MAPPING[file_type]['output_file']
                with open(output_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Find first markdown link
                    for line in lines:
                        if line.strip().startswith('['):
                            print(f"  {line.strip()}")
                            break
                break


if __name__ == "__main__":
    main()
