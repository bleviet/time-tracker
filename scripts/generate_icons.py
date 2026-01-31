import os
import subprocess
import shutil
from pathlib import Path

def run_magick(args):
    """Run imagemagick command"""
    try:
        # Check if 'magick' (v7) or 'convert' (v6) is available
        cmd = ["magick"] + args
        subprocess.run(cmd, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running magick: {e}")

def generate_icons():
    """Generate cross-platform icons from master_icon.svg using ImageMagick"""
    base_dir = Path(__file__).parent.parent
    assets_dir = base_dir / "app" / "assets"
    master_svg = assets_dir / "master_icon.svg"
    
    if not master_svg.exists():
        print(f"Error: Master SVG not found at {master_svg}")
        return

    print(f"Generating icons from {master_svg}...")

    # 1. Generate master_icon.png and clock_icon.png (general assets)
    print("Generating master_icon.png (1024x1024)...")
    run_magick(["convert", "-background", "none", str(master_svg), "-resize", "1024x1024", str(assets_dir / "master_icon.png")])
    
    print("Generating clock_icon.png (256x256)...")
    run_magick(["convert", "-background", "none", str(master_svg), "-resize", "256x256", str(assets_dir / "clock_icon.png")])

    # 2. Windows ICO
    # Best practice: 16, 32, 48, 64, 128, 256
    ico_path = assets_dir / "icon.ico"
    print(f"Generating Windows ICO: {ico_path}")
    # ImageMagick can create ICO directly containing multiple sizes
    run_magick([
        "convert", "-background", "none", str(master_svg), 
        "-define", "icon:auto-resize=256,128,64,48,32,16", 
        str(ico_path)
    ])
    
    # 3. Linux PNGs
    linux_dir = assets_dir / "linux"
    linux_dir.mkdir(exist_ok=True)
    
    linux_sizes = [16, 22, 24, 32, 48, 64, 128, 256, 512]
    print(f"Generating Linux PNGs in {linux_dir}")
    for size in linux_sizes:
        out_path = linux_dir / f"{size}x{size}.png"
        run_magick(["convert", "-background", "none", str(master_svg), "-resize", f"{size}x{size}", str(out_path)])

    # 4. macOS iconset (PNGs)
    macos_dir = assets_dir / "macos.iconset"
    macos_dir.mkdir(exist_ok=True)
    
    print(f"Generating macOS iconset in {macos_dir}")
    
    # Format: icon_{size}x{size}{@2x}.png
    macos_configs = [
        (16, 1, "icon_16x16.png"),
        (16, 2, "icon_16x16@2x.png"),
        (32, 1, "icon_32x32.png"),
        (32, 2, "icon_32x32@2x.png"),
        (128, 1, "icon_128x128.png"),
        (128, 2, "icon_128x128@2x.png"),
        (256, 1, "icon_256x256.png"),
        (256, 2, "icon_256x256@2x.png"),
        (512, 1, "icon_512x512.png"),
        (512, 2, "icon_512x512@2x.png"),
    ]
    
    for size, scale, name in macos_configs:
        final_size = size * scale
        out_path = macos_dir / name
        run_magick(["convert", "-background", "none", str(master_svg), "-resize", f"{final_size}x{final_size}", str(out_path)])

    print("Icon generation complete.")

if __name__ == "__main__":
    generate_icons()
