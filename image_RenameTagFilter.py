"""
Perform file organizing and metadata tasks for GeoTIFF files from MicaSense RedEdge.
By: Emily Sturdivant, esturdivant@usgs.gov, https://github.com/esturdivant-usgs
Requires Python 3.2+

The user inputs the following:
- input image directory (imgdir_in): directory where the raw files are stored and sorted by flight number
- output image directory (imgdir_out): directory to be created and populated with the processed files
- minimum and maximum altitude for files to process
- mission info (survey ID, camera ID, values for metadata)

Note:
- We expect flight folder names to start with 'f' and end with a number. The number in the folder name will be used as the flight ID.


This script does the following:
    1. For each flight folder copy files to a flight folder in the out dir
        1.a. Get flight IDs (integer) from the folder names in 'imgdir_in'.
        1.b. Copy TIF files in each flight folder to new flight folder in 'imgdir_in' using the naming scheme fXX, ignoring intermediate folders (e.g. 0000SET, 000)
    2. Change photo metadata: rename and assign metadata values
        2.a. Rename files with survey ID, flight ID, sensor ID, datetime, and original filename.
        2.b. Add flight ID to UserComment tag in file header.
    3. Add standard metadata values.
        3.a. Add the standard WHCMSC Exif tags, with specific values input by the user.
        3.b. Copy the CreateDate value to the GPSDate and GPSTime tags.
    4. Copy files within the input altitude range to a separate directory tree.
"""
#%%
import pandas as pd
import os
import subprocess
import shutil
import glob

#%% Set source dir
# Only used flights 11-32, i.e. photos collected on 8/7 and 8/8. RedEdge surveying on 8/6 (flights 2–10) had many gaps.
imgdir_in = r"/Volumes/stor/Projects/2019009FA_PlumIsland/RAW/photos/mica_images"
imgdir_out = r"/Volumes/stor/Projects/2019009FA_PlumIsland/PROCESSED/final_photos/micasense"

# If calibration files have already been separated out, they will need to be processed too.
cal_separated = True

# Altitude filtering values
alt_min = 73
alt_max = 88

# Mission info
fan = '2019-009-FA' # input('Field activity number (e.g. "2017-010-FA"): ')
cam_id = 'm01'
# flight_id = 'f06'
# doi =

# WHSC EXIF population
surveyid = fan.replace("-","")
site = "Plum Island, MA"
credit = "U.S. Geological Survey"
comment = """One band of a multispectral image from a low-altitude aerial survey in {1}. Captured with a MicaSense RedEdge at a target altitude of 80 m. WHCMSC field activity number {0} (https://cmgds.marine.usgs.gov/fan_info.php?fa={0}).""".format(fan, site) # used for caption, ImageDescription, Caption-Abstract
keywords = "{}; Massachusetts; {}; UAS; nadir; multispectral; USGS".format(site, fan)
artist = "WHCMSC AIM Group"
contact = "WHSC_data_contact@usgs.gov"

#%% Functions
def write_WHSC_exiftags(imgdir, credit, comment, keywords, artist, contact, run=True, recursive=True):
    # Tags that will be identical for all images in the folder
    tagvalues = {}
    tagvalues['imgdir'] = imgdir
    tagvalues['credit'] = credit
    tagvalues['artist'] = artist
    tagvalues['contact'] = contact
    tagvalues['comment'] = comment
    tagvalues['keywords'] = keywords
    tagvalues['copyright'] = "Public Domain. Please credit {credit}".format(**tagvalues)
    # Write to EXIF
    substance = """-Artist="{artist} " -Credit="{credit} " -Contact="{contact} " -comment="{comment} " -sep "; " -keywords="{keywords} " -Caption="{comment} " -Copyright="{copyright} " -CopyrightNotice="{copyright} " -Caption-Abstract="{comment} " -ImageDescription="{comment} " """.format(**tagvalues)
    tagvalues['substance'] = substance
    if run:
        if recursive:
            cmd = """exiftool {substance} -overwrite_original -r {imgdir}""".format(**tagvalues)
        else:
            cmd = """exiftool {substance} -overwrite_original {imgdir}""".format(**tagvalues)
        subprocess.check_call(cmd, shell=True)
        print("Updated Exif headers in directory: {}".format(imgdir))
        return
    else:
        return(substance)

def filter_by_exif(imgdir, keep_dir, min, max, tag='GPSAltitude'):
    # Filter image files by indicated EXIF tag. Copy files that match the criteria to a keep folder.
    # Print altitudes to CSV
    exif_csv = imgdir+"_{}.csv".format(tag)
    cmd1 = """exiftool -csv -{} -n -r {} > {}""".format(tag, imgdir, os.path.join(imgdir, exif_csv))
    subprocess.check_call(cmd1, shell=True)
    # Move photos with values between min and max (inclusive) to keep folder
    # Convert CSV To DF
    df = pd.read_csv(exif_csv)
    # for each entry, if altitude is between alt_min and alt_max (inclusive), move file to the keep folder
    keepct = 0 # keep counter
    rct = 0 # remove counter
    for index, row in df.iterrows():
        fpath = row.SourceFile
        fname = os.path.basename(row.SourceFile)
        alt = row.loc[tag]
        if alt < alt_min or alt > alt_max:
            rct += 1
        else:
            try:
                shutil.copy2(fpath, os.path.join(keep_dir, fname))
                keepct += 1
            except:
                pass
    # Print counts
    print("Files matching criteria: {} out of {}".format(keepct, keepct+rct))
    # Check altitudes - print to CSV and DF
    exif_csv = keep_dir+"_keepers.csv"
    cmd1 = """exiftool -csv -{} -n {} > {}""".format(tag, keep_dir, exif_csv)
    subprocess.check_call(cmd1, shell=True)
    df = pd.read_csv(exif_csv)
    #
    return(df)

#%% For each flight folder: get flight number, copy files to out dir, rename files
# Copy files to new flight folders, ignoring intermediate folders
print("\n***** Creating new folder structure and copying files *****".format(fnum, flight_id))
fdirs = glob.glob(os.path.join(imgdir_in, 'f*[0-9]'))
for fltdir in fdirs:
    # Convert folder name to flight ID
    fnum = int(''.join(filter(str.isdigit, os.path.basename(fltdir))))
    flight_id = 'f{0:02d}'.format(fnum)
    # Create folder for renamed photos
    print("Creating folder and copying files for flight {} ({})".format(fnum, flight_id))
    fltdir_out = os.path.join(imgdir_out, flight_id)
    try: shutil.rmtree(fltdir_out)
    except FileNotFoundError: pass
    os.makedirs(fltdir_out, exist_ok=True)
    # List TIF files and copy to processing directory, ignoring intermediate folders
    imglist = glob.glob(os.path.join(fltdir, '**/*.tif'), recursive=True)
    for img in imglist:
        shutil.copy2(img, os.path.join(fltdir_out, os.path.basename(img)))
    # Check that there are the expected number of files in the directory.
    if len(imglist) < len(os.listdir(fltdir_out)):
        print("WARNING: There are extra files in the flight directory.")
    elif len(imglist) > len(os.listdir(fltdir_out)):
        print("WARNING: There are too few files in flight directory.")

#%% Change photo metadata: Rename, Assign Exif tag values,
print("\n***** Running ExifTool for each flight folder to rename files and add flight number. *****".format(fnum, flight_id))
for fltdir_out in glob.glob(os.path.join(imgdir_out, 'f*[0-9]')):
    flight_id = os.path.basename(fltdir_out)
    num_renamed = len(glob.glob(os.path.join(fltdir_out, '{}*'.format(surveyid))))
    if num_renamed > 0:
        print("ALERT: There are already {} files in the {} folder that may have been renamed. We'll skip this folder.".format(num_renamed, flight_id))
        continue
    fnum = int(''.join(filter(str.isdigit, flight_id)))
    # Rename and save flight ID in UserComment, uses ExifTool
    cmd1 = """exiftool -d {}_{}{}_%Y%m%dT%H%M%SZ_%%f.%%e "-filename<CreateDate" -UserComment="Flight {} ; target altitude 80 m" -overwrite_original {}""".format(surveyid, cam_id, flight_id, fnum, fltdir_out)
    subprocess.check_call(cmd1, shell=True)
    print("Renamed files for flight {} ({})".format(fnum, flight_id))

#%% Get calibration images if they are in a separate dir
if cal_separated:
    indir = os.path.join(imgdir_in, 'calibration')
    fltdir_out = os.path.join(imgdir_out, 'calibration2')
    os.makedirs(fltdir_out, exist_ok=False)
    imglist = glob.glob(os.path.join(indir, '*.tif'), recursive=False)
    for img in imglist:
        shutil.copy2(img, os.path.join(fltdir_out, os.path.basename(img)))
    flight_id = 'CAL'
    cmd1 = """exiftool -d {}_{}{}_%Y%m%dT%H%M%SZ_%%f.%%e "-filename<CreateDate" -UserComment="Flight {}" -overwrite_original {}""".format(surveyid, cam_id, flight_id, flight_id, fltdir_out)
    print("Renamed calibration files (fID={})".format(flight_id))

#%% Write standard EXIF tags
# Get string to write standard EXIF tags
print("\n***** Writing standard WHSC values to EXIF tags and setting the GPSDate/Time from the CreateDate tag. *****")
whsc_tags = write_WHSC_exiftags(fltdir_out, credit, comment, keywords, artist, contact, run=False)
# Set GPSTimeStamp and GPSDateStamp from CreateDate
dt_cmd = """exiftool "-GPSTimeStamp<CreateDate" "-GPSDateStamp<CreateDate" {} -overwrite_original -r {}""".format(whsc_tags, fltdir_out)
subprocess.check_call(dt_cmd, shell=True)
print('DONE: Tag writing complete.')

#%% Execute altitude filter
# Variables: imgdir_out, alt_min, alt_max
# Function: filter_by_exif()
fdirs = glob.glob(os.path.join(imgdir_out, 'f*[0-9]'))
for fltdir_out in fdirs:
    flight_id = os.path.basename(fltdir_out)
    # Create or re-create keep_dir tree
    keep_dir = os.path.join(imgdir_out, 'keep_alt{}to{}'.format(alt_min, alt_max), flight_id)
    try: shutil.rmtree(keep_dir)
    except FileNotFoundError: pass
    os.makedirs(keep_dir, exist_ok=True)
    # Copy files within altitude bounds to keep folder
    print("Copying files matching altitude criteria to {}...".format(os.path.relpath(keep_dir, imgdir_out)))
    keeper_values = filter_by_exif(fltdir_out, keep_dir, alt_min, alt_max, tag='GPSAltitude')
    print("Number of files in final {} directory: {}".format(flight_id, len(os.listdir(keep_dir))))


# #%% Check EXIF tags
# exif_csv = imgdir_out+"_imgtags.csv"
# cmd1 = """exiftool -csv -Artist -Credit -Copyright -n -r {} > {}""".format(imgdir_out, exif_csv)
# subprocess.check_call(cmd1, shell=True)
# df = pd.read_csv(exif_csv)
# df

#%% Same process, but all in one for-loop (older version):
# #%% For each flight folder: get flight number, copy files to out dir, rename files
# # List folders
# # In each folder, rename files
# fdirs = glob.glob(os.path.join(imgdir_in, 'f*'), recursive=True)
# for fltdir in fdirs:
#     # Convert folder name to flight ID
#     fnum = int(''.join(filter(str.isdigit, os.path.basename(fltdir))))
#     flight_id = 'f{0:02d}'.format(fnum)
#     print("\n***** Processing files from flight {} ({}) *****".format(fnum, flight_id))
#     # Create folder for renamed photos
#     print("...Creating new flight folder..."
#     fltdir_out = os.path.join(imgdir_out, flight_id)
#     try: shutil.rmtree(fltdir_out)
#     except FileNotFoundError: pass
#     os.makedirs(fltdir_out, exist_ok=True)
#     # List TIF files and copy to processing directory, ignoring intermediate folders
#     imglist = glob.glob(os.path.join(fltdir, '**/*.tif'), recursive=True)
#     for img in imglist:
#         shutil.copy2(img, os.path.join(fltdir_out, os.path.basename(img)))
#     # Check that there are the expected number of files in the directory.
#     if len(imglist) < len(os.listdir(fltdir_out)):
#         print("WARNING: There are extra files in the flight directory.")
#     elif len(imglist) > len(os.listdir(fltdir_out)):
#         print("WARNING: There are too few files in flight directory.")
#     # Rename and save flight ID in UserComment, uses ExifTool
#     cmd1 = """exiftool -d {}_{}{}_%Y%m%dT%H%M%SZ_%%f.%%e "-filename<CreateDate" -UserComment="Flight {} ; target altitude 80 m" -overwrite_original {}""".format(surveyid, cam_id, flight_id, fnum, fltdir_out)
#     subprocess.check_call(cmd1, shell=True)
#     #---- Below here could be applied recursively, outside of the for loop.
#     # Get string to write standard EXIF tags
#     print("...Writing standard WHSC values to EXIF tags and setting the GPSDate/Time from the CreateDate tag...")
#     whsc_tags = write_WHSC_exiftags(fltdir_out, credit, comment, keywords, artist, contact, run=False, recursive=False)
#     # Set GPSTimeStamp and GPSDateStamp from CreateDate
#     dt_cmd = """exiftool "-GPSTimeStamp<CreateDate" "-GPSDateStamp<CreateDate" {} -overwrite_original {}""".format(whsc_tags, fltdir_out)
#     subprocess.check_call(dt_cmd, shell=True)
#     print('DONE: Tag writing completed for flight {}.'.format(flight_id))
#     # Check that there are still the same number of files in the directory.
#     if len(imglist) < len(os.listdir(fltdir_out)):
#         print("WARNING: There are extra files in the flight directory.")
#     elif len(imglist) > len(os.listdir(fltdir_out)):
#         print("WARNING: There are too few files in flight directory.")
#     #---- But not below here:
#     # Execute altitude filter
#     print("Copying files matching altitude criteria into keep folder...")
#     keep_dir = os.path.join(imgdir_out, 'keep_alt{}to{}'.format(alt_min, alt_max), flight_id)
#     os.makedirs(keep_dir, exist_ok=True) # Create keep_dir tree if it doesn't already exist.
#     # Copy files within altitude bounds to keep folder
#     keeper_values = filter_by_exif(fltdir_out, keep_dir, alt_min, alt_max, tag='GPSAltitude')
#     print("Number of files in final directory: {}".format(len(os.listdir(keep_dir))))
