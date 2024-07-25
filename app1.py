import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import PIL.ExifTags
from influx_loader import QueryInfluxData, INFLUXDB_BUCKET
import io
import zipfile
from datetime import datetime, timedelta

varMapping = pd.read_csv('InfluxDB_variables.csv')

def get_exif_data(image):
    """Extract EXIF data from an image."""
    exif_data = image._getexif()
    if exif_data is not None:
        for tag, value in exif_data.items():
            decoded_tag = PIL.ExifTags.TAGS.get(tag, tag)
            if decoded_tag == "DateTime":
                return value
    return None

def overlay_data_on_image(image, data, font_path, font_size=50):
    """Overlay data on the image."""
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()
        st.write("Failed to load specified font. Using default font.")
    
    # Prepare the text to overlay
    text = "\n".join([f"{key}: {value}" for key, value in data.items()])
    text_position = (50, 50)  # Position of the text on the image
    
    # Draw the text on the image
    draw.text(text_position, text, fill="red", font=font)
    return image

def create_zip(images, filenames):
    """Create a zip file containing the images."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for img, filename in zip(images, filenames):
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            zip_file.writestr(filename, img_byte_arr.getvalue())
    zip_buffer.seek(0)
    return zip_buffer

st.title("Photo Timestamp Extractor and Data Overlay")

uploaded_files = st.file_uploader("Choose .jpg images", type="jpg", accept_multiple_files=True)
analyze_button = st.button("Analyze")

if uploaded_files and analyze_button:
    images = []
    filenames = []

    for uploaded_file in uploaded_files:
        image = Image.open(uploaded_file)
        timestamp = get_exif_data(image)
        
        if timestamp:
            time_change = timedelta(seconds=1)
            st.write(timestamp)
            
            # st.write(f"The photo was taken at {timestamp}")
            timestamp = datetime.strptime(timestamp, '%Y:%m:%d %H:%M:%S')
            timestamp = timestamp - timedelta(hours=2)
            timestamp_start = timestamp - time_change
            # st.write(f'query from {timestamp_start} to {timestamp}')
            
            date = timestamp.strftime('%Y-%m-%d')
            fromTime_ = timestamp_start.strftime('%H:%M:%S')
            toTime_ = timestamp.strftime('%H:%M:%S')
            whereTags_ = {"boat": "AC40"}
            
            start_time = timestamp_start.isoformat() + "Z"
            end_time = timestamp.isoformat() + "Z"
            data = QueryInfluxData(INFLUXDB_BUCKET, varMapping,
                                   fromTime=datetime.strptime(f"{date} {fromTime_}", "%Y-%m-%d %H:%M:%S"),
                                   toTime=datetime.strptime(f"{date} {toTime_}", "%Y-%m-%d %H:%M:%S"),
                                   freq="1s", whereTags=whereTags_)
            
            var_test = ["TWS",'VMG%',"BSP","Tgt_BSP","TWA","AWA_bow","AWS","Leeway","Rudder_Angle",
                        "Heel","Trim","FoilCant","Flap",
                        "MainSheetLoad","Tgt_MainSheet",
                        "MainCunninghamLoad_kg","Tgt_MainCunninghamLoad_kg",
                        "JibSheetLoad","Tgt_JibSheetLoad",
                        "Tgt_FoilPort_Sink","Tgt_FoilStbd_Sink",
                        "MastRotation_angle","Traveller_angle",
                        "AverageClewPC","Link_angle"]
            data_at_timestamp = data[var_test].round(2).iloc[0].to_dict()
            
            #font_path = "/Library/Fonts/Arial.ttf"  # Adjust the path based on your OS
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            
            modified_image = overlay_data_on_image(image.copy(), data_at_timestamp, font_path, font_size=100)
            
            images.append(modified_image)
            filenames.append(uploaded_file.name)
        else:
            st.write(f"No timestamp found in {uploaded_file.name}")

    if images:
        zip_buffer = create_zip(images, filenames)
        
        st.download_button(
            label="Download ZIP of Modified Images",
            data=zip_buffer,
            file_name="modified_images.zip",
            mime="application/zip"
        )
    else:
        st.write("No valid images to process.")
