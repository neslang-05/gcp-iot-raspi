import cv2
from google.cloud import storage
from google.cloud import vision
import datetime  #for timestamp

# Google Cloud settings
BUCKET_NAME = "ocr-images-license-plates"  # Replace with your GCS bucket name
BLOB_NAME = "captured_image.jpg"  # Name for the uploaded image

def capture_and_upload_image():
    """Captures an image and uploads it to Google Cloud Storage."""
    camera = cv2.VideoCapture("http://192.168.29.207:4747/video")   
    if not camera.isOpened():
        raise IOError("Cannot open webcam")

    ret, frame = camera.read()
    camera.release()

    if ret:
        cv2.imwrite("captured_image.jpg", frame)
        print("Image captured and saved locally.")

        upload_blob(BUCKET_NAME, "captured_image.jpg", BLOB_NAME)
        print(f"Image uploaded to gs://{BUCKET_NAME}/{BLOB_NAME}")
    else:
        print("Error capturing image.")

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

def detect_license_plate(image_path):
    """Detects and extracts the license plate region."""
    # Load the image
    img = cv2.imread(image_path)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply bilateral filter to reduce noise
    blur = cv2.bilateralFilter(gray, 11, 17, 17)

    # Perform edge detection
    edged = cv2.Canny(blur, 30, 200)

    # Find contours
    cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:10]

    # Loop over contours to find the license plate
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.018 * peri, True)

        # Look for contours with 4 sides (quadrilateral)
        if len(approx) == 4:
            screenCnt = approx
            x, y, w, h = cv2.boundingRect(c)
            license_plate = img[y:y+h, x:x+w]
            return license_plate
    return None 

def perform_ocr_with_gcp(bucket_name, blob_name):
    """Performs OCR on the image using Google Cloud Vision API."""
    client = vision.ImageAnnotatorClient()
    image = vision.Image()
    image.source.image_uri = f"gs://{bucket_name}/{blob_name}"

    response = client.text_detection(image=image)
    texts = response.text_annotations

    license_plate_text = None
    for text in texts:
        # Add your license plate text filtering logic here
        # For example, check for specific patterns, lengths, etc.
        if len(text.description) >= 6:  # Example: Assume license plates have at least 6 characters
            license_plate_text = text.description
            break

    return license_plate_text

def correct_errors(text):
    """Applies basic error correction rules to the extracted text."""
    # Example: Replace common OCR errors
    text = text.replace("0", "O")  
    text = text.replace("1", "I")
    text = text.replace("8", "B")
    return text

def append_to_csv(data, filename="license_plates.csv"):
    """Appends the extracted data to a CSV file with timestamps."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filename, 'a') as csvfile:
        csvfile.write(f"{timestamp},{data}\n")  # Add timestamp before data

if __name__ == "__main__":
    capture_and_upload_image()
    image_path = "captured_image.jpg"

    license_plate_image = detect_license_plate(image_path)
    if license_plate_image is not None:
        cv2.imwrite("license_plate.jpg", license_plate_image) 
        print("License plate detected and saved.")
        
        # Perform OCR on the detected license plate region
        license_plate_text = perform_ocr_with_gcp(BUCKET_NAME, BLOB_NAME)
        if license_plate_text:
            corrected_text = correct_errors(license_plate_text)
            print("License Plate:", corrected_text)
            append_to_csv(corrected_text)
            print("License plate data appended to CSV file.")
        else:
            print("OCR could not extract license plate text.")
    else:
        print("License plate not detected.") 