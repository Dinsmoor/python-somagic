# easycap frame alternator
import os
import time
import sys
import subprocess
import Image, ImageDraw
import sys
from struct import *
import array
import schedule
import multiprocessing as mp
import threading
from datetime import datetime

if os.geteuid() != 0:
    exit("You need to have root privileges to run this script.\nExiting.")

if len(sys.argv) != 3:
        print "Usage:"
        print "# python cammanager.py <camera qty> <iter qty>"
        sys.exit(1) # exit
else:
        pass

total_cams = int(sys.argv[1])
total_iters = int(sys.argv[2])

if total_cams > 4:
    print "Maximum of 4 cams are supported"
    sys.exit(1)
if total_iters < 0:
    print "Negative iters are not supported"
    sys.exit(1)


# got help from https://shrex999.wordpress.com/2013/07/31/yuv-to-rgb-python-imaging-library/
def get_snapshot(source, iteration):

    image_name = "tmp.yuv"
    width = 720
    height = 960 #480x2 to skip first frame

    y = array.array('B')
    u = array.array('B')
    v = array.array('B')

    f_uyvy = open(image_name, "rb")
    f_uv = open(image_name, "rb")
    f_uv.seek(width*height, 1)

    image_out = Image.new("RGB", (width, height))
    pix = image_out.load()

    #720x480
    #print "width=", width, "height=", height

    for i in range(0,height):
        for j in range(0, width/2):
            u  = ord(f_uyvy.read(1));
            y1 = ord(f_uyvy.read(1));
            v  = ord(f_uyvy.read(1));
            y2 = ord(f_uyvy.read(1));

            B = 1.164 * (y1-16) + 2.018 * (u - 128)
            G = 1.164 * (y1-16) - 0.813 * (v - 128) - 0.391 * (u - 128)
            R = 1.164 * (y1-16) + 1.596*(v - 128)
            pix[j*2, i] = int(R), int(G), int(B)

            B = 1.164 * (y2-16) + 2.018 * (u - 128)
            G = 1.164 * (y2-16) - 0.813 * (v - 128) - 0.391 * (u - 128)
            R = 1.164 * (y2-16) + 1.596*(v - 128)
            pix[j*2+1, i] = int(R), int(G), int(B)

    ######################################################
    # B = 1.164(Y - 16)                   + 2.018(U - 128)
    # G = 1.164(Y - 16) - 0.813(V - 128) - 0.391(U - 128)
    # R = 1.164(Y - 16) + 1.596(V - 128)
    ######################################################

    # crop out to just the second image, shouldn't be (as) corrupt like first
    image_out = image_out.crop((0,480,720,960))
    draw = ImageDraw.Draw(image_out)
    draw.text((10,10), str(datetime.now()),(100,200,200))
    image_out.save("tmp/cam%d_%s.jpg"%(source, str(iteration).zfill(6)))
    #image_out.save("tmp/%d_current_frame.jpg"%source)

def makemovies():

    for cam in range(1, total_cams+1):
        subprocess.call("ffmpeg -y -framerate 4 -pattern_type glob -i 'tmp/cam%d*.jpg' -c:v libx264 'vid/cam_%d_%s.mp4'"%(cam,cam,str(datetime.now())))
    # too many args for normal delete
    subprocess.call("rm -rf tmp")
    subprocess.call("mkdir tmp")

def run_on_schedule():

    while True:
        schedule.run_pending()
        time.sleep(30)

def ensure_proc_dead(proc):
    proc.kill()

def collect_images():

    schedule.every(2).hours.do(makemovies)
    #schedule.every(30).seconds.do(makemovies)

    #job = mp.Process(target=run_on_schedule)
    #job.start()

    iter_num = -1
    true_iter_num = 0

    subprocess.call("somagic-init")

    while iter_num < total_iters:
        schedule.run_pending()

        if total_iters == 0:
            iter_num -= 1

        iter_num += 1
        true_iter_num += 1

        if iter_num % 50 == 0:
            subprocess.call("somagic-init")

        for source in range(1,total_cams+1):
            print "Camera", source, "Sequence", true_iter_num
            somag_proc = subprocess.Popen(["somagic-capture", "-n", "-i", "%d"%source, "-f", "2", "--vo=tmp.yuv"])
            # somagic-capture sucks ass and hangs sometimes, so we'll kill it just in case.
            t = threading.Timer(2, ensure_proc_dead, [somag_proc])
            somag_proc.wait()
            print "Extracting Frame"
            get_snapshot(source, true_iter_num)


collect_images()
