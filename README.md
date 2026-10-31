# IPP Assignment Submission Package

## Folder contents
- `workflow/google_maps_workflow.png` – Google Maps / Street View workflow diagram.
- `workflow/google_maps_workflow.mmd` – editable Mermaid source for the diagram.
- `practical_file_1/IPP_Practical_File_1.ipynb` – notebook answering all 10 basic image-processing questions.
- `practical_file_1/practical_file_1.py` – equivalent Python script.
- `practical_file_2/IPP_Practical_File_2.ipynb` – edge detection, noise, compression, JPEG artefacts, GLCM and multi-feature segmentation.
- `practical_file_2/practical_file_2.py` – equivalent Python script.
- `case_study/Google_Maps_Image_Processing_Case_Study.docx` – 10-page main report plus appendices.
- `assets/` – original synthetic demo images so code can run without downloading images.

## Setup
1. Extract the ZIP.
2. Open the extracted folder in VS Code or Jupyter.
3. Install dependencies: `pip install -r requirements.txt`
4. Open each `.ipynb` notebook and choose the Python 3 kernel.
5. Run cells from top to bottom.

## Important notes
- Practical 1 uses sample images included in `assets/`. Replace them with instructor-provided images if required.
- OpenCV display windows (`cv2.imshow`) work in a local Python desktop session. In Jupyter, use the Matplotlib display cells in the notebook.
- Your second photo is cut off at Problem 4 and Problem 6. Problem 4 is implemented as a standard JPEG quality/block-artifact comparison. Problem 6 combines the visible intensity feature with HSV colour and local texture variation. Confirm these assumptions with your instructor if possible.
- RLE/Huffman bit counts are educational payload estimates and exclude file headers and metadata.
- The disease-detection notebook is a segmentation demonstration, not a medical or agricultural diagnosis.
- Before submission, add your name, roll number, course and faculty details where required, run the notebooks, and capture your own output screenshots if your faculty asks for them.
