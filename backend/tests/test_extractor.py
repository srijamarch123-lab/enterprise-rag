import os
import unittest
from pathlib import Path
from app.services.extractor import extract_text

class ExtractorTests(unittest.TestCase):
    def setUp(self):
        self.uploads_dir = Path(r"C:\Maantic\uploads")
        if not self.uploads_dir.exists():
            self.uploads_dir = Path(__file__).parent.parent / "uploads"

    def test_extract_txt(self):
        """Test plain text extraction."""
        txt_files = list(self.uploads_dir.glob("*.txt"))
        if not txt_files:
            self.skipTest("No text files found in uploads.")
        target = txt_files[0]
        text, pages = extract_text(str(target), "txt")
        self.assertIsNotNone(text)
        self.assertTrue(len(text.strip()) > 0)
        self.assertIsNone(pages)
        print(f"\n  [TXT Extractor] Extracted {len(text)} characters from {target.name}")

    def test_extract_docx(self):
        """Test Word document extraction with a programmatically generated docx file."""
        from docx import Document
        doc = Document()
        doc.add_paragraph("Hello World from Word Document.")
        doc.add_paragraph("This is a test of python-docx extraction.")
        temp_docx = Path("temp_test_document.docx")
        try:
            doc.save(str(temp_docx))
            
            # Extract text
            text, pages = extract_text(str(temp_docx), "docx")
            self.assertIsNotNone(text)
            self.assertIn("Hello World from Word Document", text)
            self.assertIn("python-docx extraction", text)
            self.assertIsNone(pages)
            print(f"\n  [DOCX Extractor] Successfully extracted text: {text.strip()}")
        finally:
            if temp_docx.exists():
                os.remove(temp_docx)

    def test_extract_native_pdf(self):
        """Test native character-based PDF text extraction."""
        # Finance - Budget Report or HR Employee Handbook are usually native PDFs
        native_files = [f for f in self.uploads_dir.glob("*.pdf") if "Scanned" not in f.name and "Invoice" not in f.name]
        if not native_files:
            self.skipTest("No native PDF files found in uploads.")
        target = native_files[0]
        text, pages = extract_text(str(target), "pdf")
        self.assertIsNotNone(text)
        self.assertTrue(len(text.strip()) > 0)
        self.assertTrue(pages > 0)
        print(f"\n  [Native PDF Extractor] Extracted {len(text)} characters from {target.name} ({pages} pages)")

    def test_extract_scanned_pdf_ocr(self):
        """Test scanned PDF extraction using local OCR fallback."""
        scanned_files = [f for f in self.uploads_dir.glob("*.pdf") if "Scanned" in f.name or "Invoice" in f.name]
        if not scanned_files:
            self.skipTest("No scanned/invoice PDF files found in uploads.")
        target = scanned_files[0]
        text, pages = extract_text(str(target), "pdf")
        self.assertIsNotNone(text)
        self.assertTrue(len(text.strip()) > 0)
        self.assertTrue(pages > 0)
        print(f"\n  [OCR PDF Extractor] Extracted {len(text)} characters from {target.name} ({pages} pages)")

    def test_extract_pptx(self):
        """Test presentation file extraction with a programmatically generated pptx file."""
        from pptx import Presentation
        prs = Presentation()
        # Add a slide
        slide_layout = prs.slide_layouts[0] # title layout
        slide = prs.slides.add_slide(slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = "Hello World Presentation"
        subtitle.text = "This is a test of python-pptx extraction."

        temp_pptx = Path("temp_test_presentation.pptx")
        try:
            prs.save(str(temp_pptx))
            
            # Extract text
            text, pages = extract_text(str(temp_pptx), "pptx")
            self.assertIsNotNone(text)
            self.assertIn("Hello World Presentation", text)
            self.assertIn("python-pptx extraction", text)
            self.assertEqual(pages, 1)
            print(f"\n  [TXT Extractor] Successfully extracted text from PPTX: {text.strip()}")
        finally:
            if temp_pptx.exists():
                os.remove(temp_pptx)

    def test_extract_image(self):
        """Test image character extraction using Pillow and pytesseract OCR."""
        from PIL import Image, ImageDraw
        
        # Create a simple white image
        img = Image.new("RGB", (300, 100), color="white")
        d = ImageDraw.Draw(img)
        # Using default bitmap font
        d.text((10, 10), "Hello", fill="black")
        
        temp_img = Path("temp_test_image.png")
        try:
            img.save(str(temp_img))
            
            # Extract text
            text, pages = extract_text(str(temp_img), "png")
            self.assertIsNotNone(text)
            self.assertIn("Hello", text)
            self.assertIsNone(pages)
            print(f"\n  [Image OCR Extractor] Successfully extracted text from image: {text.strip()}")
        finally:
            if temp_img.exists():
                os.remove(temp_img)

    def test_extract_xlsx(self):
        """Test Excel document extraction with a programmatically generated xlsx file."""
        import xlsxwriter
        
        temp_xlsx = Path("temp_test_document.xlsx")
        workbook = xlsxwriter.Workbook(str(temp_xlsx))
        worksheet = workbook.add_worksheet("Sheet1")
        worksheet.write_row(0, 0, ["Name", "Age", "Department"])
        worksheet.write_row(1, 0, ["Alice", 25, "HR"])
        worksheet.write_row(2, 0, ["Bob", 30, "Engineering"])
        workbook.close()
        
        try:
            # Extract text
            text, pages = extract_text(str(temp_xlsx), "xlsx")
            self.assertIsNotNone(text)
            self.assertIn("--- Sheet: Sheet1 ---", text)
            self.assertIn("Name | Age | Department", text)
            self.assertIn("Alice | 25 | HR", text)
            self.assertIn("Bob | 30 | Engineering", text)
            self.assertIsNone(pages)
            print(f"\n  [XLSX Extractor] Successfully extracted text: {text.strip()}")
        finally:
            if temp_xlsx.exists():
                os.remove(temp_xlsx)

    def test_extract_rtf(self):
        """Test RTF document extraction with programmatically generated rtf file."""
        rtf_content = r"{\rtf1\ansi\deff0 {\fonttbl {\f0 Courier;}}\f0\fs24 Hello from RTF document.}"
        temp_rtf = Path("temp_test_document.rtf")
        try:
            temp_rtf.write_text(rtf_content, encoding="utf-8")
            text, pages = extract_text(str(temp_rtf), "rtf")
            self.assertIsNotNone(text)
            self.assertIn("Hello from RTF document.", text)
            self.assertIsNone(pages)
            print(f"\n  [RTF Extractor] Successfully extracted text: {text.strip()}")
        finally:
            if temp_rtf.exists():
                os.remove(temp_rtf)

if __name__ == "__main__":
    unittest.main()
