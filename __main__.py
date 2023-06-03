from collections import namedtuple
import argparse
import cv2
import re
import time
import sys
import os
import numpy as np
from datetime import timedelta

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--geometry', required=True, type=str, help='Geometry in pixels where the dialog should appear (WxH+X+Y)')
    parser.add_argument('-i', '--input', required=True, type=str, help='Input video file or a still frame')
    parser.add_argument('-ss', '--start', default=0, type=int, help='Start from this frame')
    parser.add_argument('-n', '--threads', default=None, type=int, help='How many CPU threads to use. (Defaults to all)')
    parser.add_argument('output', nargs='?', type=str, help='Path to output detected timestamps. Defaults to stdout.', default=None)
    args = parser.parse_args()

    # state management
    config = {
        'mode': None,
        'geometry': None,
        'input': args.input,
        'output': args.output,
        'start': args.start,
        'threads': None
    }

    # special mode for picking the geometry from video using GUI
    if args.geometry == 'pick':
        config['mode'] = 'pick'
    else:
        # check if the geometry is in a valid format
        match = re.findall(r'(\d+)x(\d+)\+(\d+)\+(\d+)', args.geometry)
        if match is None or len(match) != 1 or len(match[0]) != 4:
            raise SyntaxError('Geometry argument is in an invalid format')
        width, height, x, y = [int(x) for x in match[0]]

        # ensure that it somewhat makes sense (logically)
        if x < 0 or y < 0 or width < 0 or height < 0:
            raise SyntaxError('Geometry values are invalid')

        config['mode'] = 'process'
        config['geometry'] = namedtuple('Geometry', ['width', 'height', 'x', 'y'])(width, height, x, y)
        config['threads'] = config['threads'] if config['threads'] is not None else os.cpu_count()

    # load the given video
    capture: cv2.VideoCapture = cv2.VideoCapture(config['input'])
    capture.set(cv2.CAP_PROP_POS_FRAMES, config['start'])
    vWidth, vHeight = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    vFrames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

    # if the mode is 'pick', just show a very simplistic "player" that displays pixel position
    if config['mode'] == 'pick':
        cv2.namedWindow('picker', cv2.WINDOW_NORMAL)

        # to drag and create the geometry
        def mouse_handler(event, x, y, flags, data):
            if event == cv2.EVENT_LBUTTONDOWN:
                data['start'] = (x, y)
                data['end'] = None
            elif event == cv2.EVENT_LBUTTONUP:
                data['end'] = (x, y)
                if data['start'][0] <= data['end'][0] and data['start'][1] <= data['end'][1]:
                    topleft = data['start']
                    bottomright = data['end']
                else:
                    topleft = data['end']
                    bottomright = data['start']
                print(f'{bottomright[0]-topleft[0]}x{bottomright[1]-topleft[1]}+{topleft[0]}+{topleft[1]}')
                data['clean'] = True
        
        # shared data for the mouse callback as well
        rect = { 'start': (0, 0), 'end': None, 'clean': False }
        cv2.setMouseCallback('picker', mouse_handler, rect)

        # slider for video position
        def position_change(position):
            capture.set(cv2.CAP_PROP_POS_FRAMES, position)
            rect['clean'] = True
        
        # note: we don't update this since (by default) it is quite taxing to do so
        cv2.createTrackbar('videopos', 'picker', 0, vFrames, position_change)

        playback = True
        while(capture.isOpened):
            if rect['clean']: # rect was changed, clean slate please
                ret, frame = capture.retrieve()
            if playback:
                framepos = int(capture.get(cv2.CAP_PROP_POS_FRAMES)) # loop instead of crashing pls
                if framepos == vFrames: capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                else: ret, frame = capture.read()
            if rect['end'] is not None: cv2.rectangle(frame, rect['start'], rect['end'], (0, 255, 0), 2)
            cv2.imshow('picker', frame)

            framepos = int(capture.get(cv2.CAP_PROP_POS_FRAMES))

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                playback = not playback
                cv2.setTrackbarPos('videopos', 'picker', framepos)
            elif key == 81:
                cv2.setTrackbarPos('videopos', 'picker', framepos - 1)
            elif key == 83:
                cv2.setTrackbarPos('videopos', 'picker', framepos + 1)
    elif config['mode'] == 'process':
        # validate geometry again
        if config['geometry'].width + config['geometry'].x > vWidth or config['geometry'].height + config['geometry'].y > vHeight:
            raise ValueError('Geometry is out of bounds from video')

        # set the output
        file = open(config['output'], 'w') if config['output'] else None
        if file is not None: file.write('frame;value\n') # CSV header

        # kernel for fixing compression bias
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2,2))
        
        # debug outputting
        startTime = time.time()
        lastDebug = startTime
        lastPeriod = 30.0 # every 30 seconds
        lastProcessed = 0
        totalProcesed = config['start']

        frame = None
        freeze = False
        step = False

        # set CPU thread count
        cv2.setNumThreads(config['threads'])

        # deconstruct the geometry again...
        width, height, x, y = config['geometry']
        geometry_pixelarea = width * height

        # process per-frame
        while(capture.isOpened):
            framepos = totalProcesed # int(capture.get(cv2.CAP_PROP_POS_FRAMES))
            if framepos == vFrames: break
            
            if frame is None or step or not freeze: ret, frame = capture.read()
            if step: step = False

            # the "Save" button lights up brightly upon clicking, so checking every frame that it happens
            # Game is running on 30 FPS so technically we shouldn't miss it even with a 720p30 stream
            # The threshold values are 200, which is *very* lax, so I expect some incorrect detections.
            cropped = cv2.cvtColor(frame[
                y:y+height,
                x:x+width
            ], cv2.COLOR_BGR2HSV)
            # ret, gray = cv2.threshold(cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY), 200, 255, cv2.THRESH_BINARY)
            gray = cv2.inRange(cropped, (20, 20, 200), (40, 40, 255))
            # so the measured values RGB = 255, 30, 30 -> HSV? 
            # so in BGR that'd be SVH...?

            # cv2.imshow('frame', np.vstack([cropped, cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)]))

            # To fill in small pixel-gaps due to compression
            value = cv2.sumElems(cv2.dilate(gray, kernel))[0] / geometry_pixelarea

            # If the value is triggered, just print out the value
            if value >= 250.0:
                line = f'{framepos};{value}'
                if file is not None:
                    file.write(f'{line}\n')
                    file.flush()
                else: print(line)

            # Debug so we don't get insane
            lastProcessed = lastProcessed + 1
            totalProcesed = totalProcesed + 1
            currTime = time.time()
            if currTime - lastDebug >= lastPeriod:
                rate = float(lastProcessed) / lastPeriod
                eta = (vFrames - totalProcesed) / rate
                relative = float(totalProcesed) / vFrames * 100.0
                print(f'[DBG] ({relative:.2f}%) Processed {totalProcesed}/{vFrames} frames ({rate:.2f} FPS) (ETA: {str(timedelta(seconds=int(eta)))} seconds)', file=sys.stderr)
                lastProcessed = 0
                lastDebug = currTime

            # key = cv2.waitKey(1) & 0xFF
            # if key == ord('q'):
            #     break
            # if key == ord('d'):
            #     step = True
            # if key == ord(' '):
            #     freeze = not freeze
        if file: file.close()
        print(f'[DBG] Finished, it took {(time.time() - startTime):.2f} seconds', file=sys.stderr)

    # cleanup
    capture.release()
    cv2.destroyAllWindows()
