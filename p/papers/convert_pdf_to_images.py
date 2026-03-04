from pdf2image import convert_from_path
import os

pdf_dir = "/home/quan/testdata/aspipe_v4/p/papers"
output_dir = "/home/quan/testdata/aspipe_v4/p/papers/images"

# Get all PDF files
pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]

for pdf_file in pdf_files:
    pdf_path = os.path.join(pdf_dir, pdf_file)
    filename = os.path.splitext(pdf_file)[0]

    print(f"Converting: {filename}")

    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=150)

        # Save each page as an image
        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f"{filename}_page_{i+1:03d}.png")
            image.save(image_path, 'PNG')

        print(f"  ✓ Converted {len(images)} pages")
    except Exception as e:
        print(f"  ✗ Error: {e}")

print("\nConversion complete!")
