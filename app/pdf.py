# pdf_worker.py
import sys
import os
from playwright.sync_api import sync_playwright

def log_message(msg):
    print(msg, flush=True)

def convert_html_to_pdf(html_in, pdf_out, pdf_size, top_margin, bottom_margin):
    log_message("Starting PDF generation")

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            except Exception as e:
                log_message(f"🚫 Failed to launch browser: {e}")
                return
            page = browser.new_page()

            abs_html_path = f"file://{os.path.abspath(html_in)}"
            page.goto(abs_html_path)

            # Ensure the output PDF path is absolute and points to the correct directory
            abs_pdf_path = os.path.abspath(pdf_out)
            page.pdf(path=abs_pdf_path, format=pdf_size, margin={"top": top_margin, "bottom": bottom_margin})
            browser.close()
            log_message(f"✅ PDF saved at {abs_pdf_path}")

    except Exception as e:
        log_message(f"🔥 Top-level error in PDF generation: {e}")

if __name__ == "__main__":
    html_in = sys.argv[1]
    pdf_out = sys.argv[2]
    pdf_size = sys.argv[3]
    top_margin = sys.argv[4]
    bottom_margin = sys.argv[5]

    convert_html_to_pdf(html_in, pdf_out, pdf_size, top_margin, bottom_margin)
