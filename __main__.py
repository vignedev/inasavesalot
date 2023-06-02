from collections import namedtuple
import argparse
import cv2
import re

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--geometry', required=True, type=str, help='Geometry in pixels where the dialog should appear (WxH+X+Y)')
    parser.add_argument('-i', '--input', required=True, type=str, help='Input video file or a still frame')
    parser.add_argument('output', nargs='?', type=str, help='Path to output detected timestamps. Defaults to stdout.', default=None)
    args = parser.parse_args()

    # state management
    config = {
        'mode': None,
        'geometry': None,
        'input': args.input,
        'output': args.output
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

    # load the given video
    capture: cv2.VideoCapture = cv2.VideoCapture(config['input'])
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

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                playback = not playback
                cv2.setTrackbarPos('videopos', 'picker', int(capture.get(cv2.CAP_PROP_POS_FRAMES)))
    elif config['mode'] == 'process':
        # validate geometry again
        if config['geometry'].width + config['geometry'].x > vWidth or config['geometry'].height + config['geometry'].y > vHeight:
            raise ValueError('Geometry is out of bounds from video')

        playback = True
        forceUpdate = False
        thresholdMode = True
        frameUpdated = False

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2,2))

        cv2.namedWindow('debug', cv2.WINDOW_NORMAL)
        def position_change(position):
            global forceUpdate
            capture.set(cv2.CAP_PROP_POS_FRAMES, position)
            forceUpdate = True

        capture.set(cv2.CAP_PROP_POS_FRAMES, 264792)
        playback = False

        cv2.createTrackbar('videopos', 'debug', int(capture.get(cv2.CAP_PROP_POS_FRAMES)), vFrames, position_change)

        while(capture.isOpened):
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                playback = not playback
                cv2.setTrackbarPos('videopos', 'debug', framepos)
            elif key == ord('a'):
                thresholdMode = not thresholdMode
                forceUpdate = True
            elif key == 81:
                capture.set(cv2.CAP_PROP_POS_FRAMES, framepos - 1)
                cv2.setTrackbarPos('videopos', 'debug', int(capture.get(cv2.CAP_PROP_POS_FRAMES)))
            elif key == 83:
                capture.set(cv2.CAP_PROP_POS_FRAMES, framepos + 1)
                cv2.setTrackbarPos('videopos', 'debug', int(capture.get(cv2.CAP_PROP_POS_FRAMES)))

            if forceUpdate:
                ret, frame = capture.retrieve()
                frameUpdated = True
                forceUpdate = False
            elif playback:
                if int(capture.get(cv2.CAP_PROP_POS_FRAMES)) == vFrames:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0) # loop dont't crash onegai/bitte/please
                ret, frame = capture.read()
                frameUpdated = True
            framepos = int(capture.get(cv2.CAP_PROP_POS_FRAMES)) # update the expected value

            # calculation of bright parts
            if frameUpdated:
                ret, gray = cv2.threshold(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), 230, 255, cv2.THRESH_BINARY)
                cropped = cv2.dilate(gray[
                    config['geometry'].y:config['geometry'].y+config['geometry'].height,
                    config['geometry'].x:config['geometry'].x+config['geometry'].width
                ], kernel)
                value = cv2.sumElems(cropped)[0] / (config['geometry'].width * config['geometry'].height)

                if thresholdMode:
                    gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
                    cv2.putText(gray, 'threshold_mode', (0, vHeight), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.0, (255, 255, 0), 1, cv2.LINE_AA)
                    frame = gray

                cv2.putText(frame, str(value), (0, 24), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.0, (255, 255, 0), 1, cv2.LINE_AA)
                cv2.rectangle(frame, (config['geometry'].x, config['geometry'].y), (config['geometry'].x + config['geometry'].width, config['geometry'].y + config['geometry'].height), (0, 255, 0), 2)
            
            frameUpdated = False
            cv2.imshow('debug', frame)
        pass

    # cleanup
    capture.release()
    cv2.destroyAllWindows()