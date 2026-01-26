import os
from pathlib import Path
from PIL import Image

def generate_icons():
    """Generate cross-platform icons from master_icon.png"""
    base_dir = Path(__file__).parent.parent
    assets_dir = base_dir / "app" / "assets"
    master_path = assets_dir / "master_icon.png"
    
    if not master_path.exists():
        print(f"Error: Master icon not found at {master_path}")
        return

    img = Image.open(master_path)
    
    # 1. Windows ICO
    # Best practice: 16, 32, 48, 64, 256
    windows_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)]
    ico_path = assets_dir / "icon.ico"
    print(f"Generating Windows ICO: {ico_path}")
    img.save(ico_path, format='ICO', sizes=windows_sizes)
    
    # 2. Linux PNGs
    linux_dir = assets_dir / "linux"
    linux_dir.mkdir(exist_ok=True)
    
    linux_sizes = [16, 22, 24, 32, 48, 64, 128, 256, 512]
    print(f"Generating Linux PNGs in {linux_dir}")
    for size in linux_sizes:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(linux_dir / f"{size}x{size}.png")

    # 3. macOS iconset (PNGs)
    # macOS typically uses .icns which is a specific container. 
    # Pillow doesn't write .icns natively well.
    # We will generate the iconset folder structure which can be converted using iconutil on macOS.
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
        if final_size > 1024:
            continue # Skip if master is smaller, but our master is 1024, so it's fine.
            
        resized = img.resize((final_size, final_size), Image.Resampling.LANCZOS)
        resized.save(macos_dir / name)

    print("Icon generation complete.")

if __name__ == "__main__":
    generate_icons()
