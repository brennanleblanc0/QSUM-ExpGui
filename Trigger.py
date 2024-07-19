# coding=utf-8
# =============================================================================
# Copyright (c) 2001-2024 FLIR Systems, Inc. All Rights Reserved.
#
# This software is the confidential and proprietary information of FLIR
# Integrated Imaging Solutions, Inc. ("Confidential Information"). You
# shall not disclose such Confidential Information and shall use it only in
# accordance with the terms of the license agreement you entered into
# with FLIR Integrated Imaging Solutions, Inc. (FLIR).
#
# FLIR MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT THE SUITABILITY OF THE
# SOFTWARE, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE, OR NON-INFRINGEMENT. FLIR SHALL NOT BE LIABLE FOR ANY DAMAGES
# SUFFERED BY LICENSEE AS A RESULT OF USING, MODIFYING OR DISTRIBUTING
# THIS SOFTWARE OR ITS DERIVATIVES.
# =============================================================================
#
# Trigger.py shows how to trigger the camera. It relies on information
# provided in the Enumeration, Acquisition, and NodeMapInfo examples.
#
# It can also be helpful to familiarize yourself with the ImageFormatControl
# and Exposure examples. As they are somewhat shorter and simpler, either
# provides a strong introduction to camera customization.
#
# This example shows the process of configuring, using, and cleaning up a
# camera for use with both a software and a hardware trigger.
#
# Please leave us feedback at: https://www.surveymonkey.com/r/TDYMVAPI
# More source code examples at: https://github.com/Teledyne-MV/Spinnaker-Examples
# Need help? Check out our forum at: https://teledynevisionsolutions.zendesk.com/hc/en-us/community/topics

import os
import PySpin
import sys
import threading
import time
import MotTemp
import math
import numpy as np

class TriggerType:
    SOFTWARE = 1
    HARDWARE = 2


CHOSEN_TRIGGER = TriggerType.HARDWARE

class CamTrigger(threading.Thread):
    def __init__(self, numImages, trigPath, exposureTime, timeSplit, window):
        threading.Thread.__init__(self, daemon=True)
        self.numImages = numImages
        self.trigPath = trigPath
        self.exposureTime = exposureTime
        self.timeSplit = timeSplit
        self.window = window
    def run(self):
        self.main()
    def drawStdDev(self, image_in):
        image = np.copy(image_in)
        binx = []
        biny = []
        peakX = 0
        peakY = 0
        for i in range(0,len(image)):
            intensity = 0
            for j in range(0, len(image[0])):
                intensity += image[i][j]
            biny.append(intensity)
            if biny[peakY] < intensity:
                peakY = len(biny) - 1

        for j in range(0, len(image[0])):
            intensity = 0
            for i in range(0, len(image)):
                intensity += image[i][j]
            binx.append(intensity)
            if binx[peakX] < intensity:
                peakX = len(binx) - 1

        x1d = []
        xsum = 0
        y1d = []
        ysum = 0
        for j in range(0, len(image[peakY])):
            x1d.append(image[peakY][j])
            xsum += image[peakY][j]
        for i in range(0, len(image)):
            y1d.append(image[i][peakX])
            ysum += image[i][peakX]
    
        px = []
        py = []
        mux = 0
        muy = 0

        for i in range(0, len(x1d)):
            px.append(x1d[i]/xsum)
            mux += px[i] * i

        for i in range(0, len(y1d)):
            py.append(y1d[i]/ysum)
            muy += py[i] * i

        stdx = 0
        stdy = 0

        for i in range(0, len(px)):
            stdx += px[i] * (i - mux)**2
        for i in range(0, len(py)):
            stdy += py[i] * (i - muy)**2
        
        stdx = math.sqrt(stdx)
        stdy = math.sqrt(stdy)

        for j in range(max(0, math.floor(peakX - (stdx*3))), min(len(image[peakY]), math.floor(peakX + (stdx*3)))):
            image[peakY][j] = 65535
        for i in range(max(0, math.floor(peakY - (stdy*3))), min(len(image), math.floor(peakY + (stdy*3))+1)):
            image[i][peakX] = 65535

        for i in range(len(image)):
            image[i][peakX] = 65535
        for j in range(len(image[0])):
            image[peakY][j] = 65535

        y1d.reverse()
        self.window.camWidget.axes[1].plot(range(len(x1d)), x1d)
        self.window.camWidget.axes[2].plot(y1d, range(len(y1d)))

        self.window.camWidget.axes[0].imshow(image, cmap="gray")
        self.window.camWidget.axes[0].title.set_text("Camera View")
        self.window.camWidget.axes[1].title.set_text("X-Axis Profile")
        self.window.camWidget.axes[2].title.set_text("Y-Axis Profile")
        self.window.camWidget.draw()
        self.window.camWidget.axes[0].cla()
        self.window.camWidget.axes[1].cla()
        self.window.camWidget.axes[2].cla()
    def configure_trigger(self, cam):
        """
        This function configures the camera to use a trigger. First, trigger mode is
        set to off in order to select the trigger source. Once the trigger source
        has been selected, trigger mode is then enabled, which has the camera
        capture only a single image upon the execution of the chosen trigger.

        :param cam: Camera to configure trigger for.
        :type cam: CameraPtr
        :return: True if successful, False otherwise.
        :rtype: bool
        """
        result = True

        print('*** CONFIGURING TRIGGER ***\n')

        print('Note that if the application / user software triggers faster than frame time, the trigger may be dropped / skipped by the camera.\n')
        print('If several frames are needed per trigger, a more reliable alternative for such case, is to use the multi-frame mode.\n\n')

        if CHOSEN_TRIGGER == TriggerType.SOFTWARE:
            print('Software trigger chosen ...')
        elif CHOSEN_TRIGGER == TriggerType.HARDWARE:
            print('Hardware trigger chose ...')

        try:
            if cam.PixelFormat.GetAccessMode() == PySpin.RW:
                cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono16)
                print('Pixel format set to %s...' % cam.PixelFormat.GetCurrentEntry().GetSymbolic())

            else:
                print('Pixel format not available...')
                return False

            if cam.ExposureAuto.GetAccessMode() != PySpin.RW:
                print('Unable to disable automatic exposure. Aborting...')
                return False
            
            cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            print('Automatic exposure disabled...')

            if cam.ExposureTime.GetAccessMode() != PySpin.RW:
                print('Unable to set exposure time. Aborting...')
                return False

            # Ensure desired exposure time does not exceed the maximum
            cam.ExposureTime.SetValue(float(self.exposureTime))
            print('Shutter time set to %s us...\n' % self.exposureTime)

            # Ensure trigger mode off
            # The trigger must be disabled in order to configure whether the source
            # is software or hardware.
            nodemap = cam.GetNodeMap()
            node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
            if not PySpin.IsReadable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
                print('Unable to disable trigger mode (node retrieval). Aborting...')
                return False

            node_trigger_mode_off = node_trigger_mode.GetEntryByName('Off')
            if not PySpin.IsReadable(node_trigger_mode_off):
                print('Unable to disable trigger mode (enum entry retrieval). Aborting...')
                return False

            node_trigger_mode.SetIntValue(node_trigger_mode_off.GetValue())

            print('Trigger mode disabled...')

            # Set TriggerSelector to FrameStart
            # For this example, the trigger selector should be set to frame start.
            # This is the default for most cameras.
            node_trigger_selector= PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSelector'))
            if not PySpin.IsReadable(node_trigger_selector) or not PySpin.IsWritable(node_trigger_selector):
                print('Unable to get trigger selector (node retrieval). Aborting...')
                return False

            node_trigger_selector_framestart = node_trigger_selector.GetEntryByName('FrameStart')
            if not PySpin.IsReadable(node_trigger_selector_framestart):
                print('Unable to set trigger selector (enum entry retrieval). Aborting...')
                return False
            node_trigger_selector.SetIntValue(node_trigger_selector_framestart.GetValue())

            print('Trigger selector set to frame start...')

            # Select trigger source
            # The trigger source must be set to hardware or software while trigger
            # mode is off.
            node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
            if not PySpin.IsReadable(node_trigger_source) or not PySpin.IsWritable(node_trigger_source):
                print('Unable to get trigger source (node retrieval). Aborting...')
                return False

            if CHOSEN_TRIGGER == TriggerType.SOFTWARE:
                node_trigger_source_software = node_trigger_source.GetEntryByName('Software')
                if not PySpin.IsReadable(node_trigger_source_software):
                    print('Unable to get trigger source (enum entry retrieval). Aborting...')
                    return False
                node_trigger_source.SetIntValue(node_trigger_source_software.GetValue())
                print('Trigger source set to software...')

            elif CHOSEN_TRIGGER == TriggerType.HARDWARE:
                node_trigger_source_hardware = node_trigger_source.GetEntryByName('Line3')
                if not PySpin.IsReadable(node_trigger_source_hardware):
                    print('Unable to get trigger source (enum entry retrieval). Aborting...')
                    return False
                node_trigger_source.SetIntValue(node_trigger_source_hardware.GetValue())
                print('Trigger source set to hardware...')

            # Turn trigger mode on
            # Once the appropriate trigger source has been set, turn trigger mode
            # on in order to retrieve images using the trigger.
            node_trigger_mode_on = node_trigger_mode.GetEntryByName('On')
            if not PySpin.IsReadable(node_trigger_mode_on):
                print('Unable to enable trigger mode (enum entry retrieval). Aborting...')
                return False

            node_trigger_mode.SetIntValue(node_trigger_mode_on.GetValue())
            print('Trigger mode turned back on...')

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False

        return result


    def grab_next_image_by_trigger(self, nodemap:PySpin.INodeMap, cam):
        """
        This function acquires an image by executing the trigger node.

        :param cam: Camera to acquire images from.
        :param nodemap: Device nodemap.
        :type cam: CameraPtr
        :type nodemap: INodeMap
        :return: True if successful, False otherwise.
        :rtype: bool
        """
        try:
            result = True
            # Use trigger to capture image
            # The software trigger only feigns being executed by the Enter key;
            # what might not be immediately apparent is that there is not a
            # continuous stream of images being captured; in other examples that
            # acquire images, the camera captures a continuous stream of images.
            # When an image is retrieved, it is plucked from the stream.

            if CHOSEN_TRIGGER == TriggerType.SOFTWARE:
                # Get user input
                input('Press the Enter key to initiate software trigger.')

                # Execute software trigger
                node_softwaretrigger_cmd = PySpin.CCommandPtr(nodemap.GetNode('TriggerSoftware'))
                if not PySpin.IsWritable(node_softwaretrigger_cmd):
                    print('Unable to execute trigger. Aborting...')
                    return False

                node_softwaretrigger_cmd.Execute()

                # TODO: Blackfly and Flea3 GEV cameras need 2 second delay after software trigger

            elif CHOSEN_TRIGGER == TriggerType.HARDWARE:
                print('Use the hardware to trigger image acquisition.')

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False

        return result


    def acquire_images(self, cam:PySpin.CameraPtr, nodemap, nodemap_tldevice):
        """
        This function acquires and saves 10 images from a device.
        Please see Acquisition example for more in-depth comments on acquiring images.

        :param cam: Camera to acquire images from.
        :param nodemap: Device nodemap.
        :param nodemap_tldevice: Transport layer device nodemap.
        :type cam: CameraPtr
        :type nodemap: INodeMap
        :type nodemap_tldevice: INodeMap
        :return: True if successful, False otherwise.
        :rtype: bool
        """

        print('*** IMAGE ACQUISITION ***\n')
        try:
            result = True

            # Set acquisition mode to continuous
            # In order to access the node entries, they have to be casted to a pointer type (CEnumerationPtr here)
            node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
            if not PySpin.IsReadable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
                print('Unable to set acquisition mode to continuous (enum retrieval). Aborting...')
                return False

            # Retrieve entry node from enumeration node
            node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
            if not PySpin.IsReadable(node_acquisition_mode_continuous):
                print('Unable to set acquisition mode to continuous (entry retrieval). Aborting...')
                return False

            # Retrieve integer value from entry node
            acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()

            # Set integer value from entry node as new value of enumeration node
            node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

            print('Acquisition mode set to continuous...')

            #  Begin acquiring images
            cam.BeginAcquisition()

            print('Acquiring images...')

            #  Retrieve device serial number for filename
            #
            #  *** NOTES ***
            #  The device serial number is retrieved in order to keep cameras from
            #  overwriting one another. Grabbing image IDs could also accomplish
            #  this.
            device_serial_number = ''
            node_device_serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
            if PySpin.IsReadable(node_device_serial_number):
                device_serial_number = node_device_serial_number.GetValue()
                print('Device serial number retrieved as %s...' % device_serial_number)

            # Retrieve, convert, and save images

            # Create ImageProcessor instance for post processing images
            #processor = PySpin.ImageProcessor()

            # Set default image processor color processing method
            #
            # *** NOTES ***
            # By default, if no specific color processing algorithm is set, the image
            # processor will default to NEAREST_NEIGHBOR method.
            #processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)

            for i in range(self.numImages):
                try:

                    #  Retrieve the next image from the trigger
                    result &= self.grab_next_image_by_trigger(nodemap, cam)

                    #  Retrieve next received image
                    image_result:PySpin.ImagePtr = cam.GetNextImage(10000)

                    #  Ensure image completion
                    if image_result.IsIncomplete():
                        print('Image incomplete with image status %d ...' % image_result.GetImageStatus())

                    else:

                        #  Print image information; height and width recorded in pixels
                        #
                        #  *** NOTES ***
                        #  Images have quite a bit of available metadata including
                        #  things such as CRC, image status, and offset values, to
                        #  name a few.
                        width = image_result.GetWidth()
                        height = image_result.GetHeight()
                        print('Grabbed Image %d, width = %d, height = %d' % (i, width, height))

                        #  Convert image to mono 8
                        #
                        #  *** NOTES ***
                        #  Images can be converted between pixel formats by using
                        #  the appropriate enumeration value. Unlike the original
                        #  image, the converted one does not need to be released as
                        #  it does not affect the camera buffer.
                        #
                        #  When converting images, color processing algorithm is an
                        #  optional parameter.
                        #image_converted = processor.Convert(image_result, PySpin.PixelFormat_Mono8)

                        # Create a unique filename
                        filename = f'CloudDetection_TOF-{self.timeSplit[i]}ms.tiff'

                        # Save image
                        #
                        #  *** NOTES ***
                        #  The standard practice of the examples is to use device
                        #  serial numbers to keep images of one device from
                        #  overwriting those of another.
                        image_result.Save(f"{self.trigPath}{filename}", PySpin.TIFFOption())
                        print('Image saved at %s\n' % filename)

                        image_np = image_result.GetNDArray()

                        self.drawStdDev(image_np)

                        #  Release image
                        #
                        #  *** NOTES ***
                        #  Images retrieved directly from the camera (i.e. non-converted
                        #  images) need to be released in order to keep from filling the
                        #  buffer.
                        image_result.Release()

                except PySpin.SpinnakerException as ex:
                    print('Error: %s' % ex)
                    return False

            # End acquisition
            #
            #  *** NOTES ***
            #  Ending acquisition appropriately helps ensure that devices clean up
            #  properly and do not need to be power-cycled to maintain integrity.
            cam.EndAcquisition()

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False

        return result


    def reset_trigger(self, nodemap):
        """
        This function returns the camera to a normal state by turning off trigger mode.

        :param nodemap: Transport layer device nodemap.
        :type nodemap: INodeMap
        :returns: True if successful, False otherwise.
        :rtype: bool
        """
        try:
            result = True
            node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
            if not PySpin.IsReadable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
                print('Unable to disable trigger mode (node retrieval). Aborting...')
                return False

            node_trigger_mode_off = node_trigger_mode.GetEntryByName('Off')
            if not PySpin.IsReadable(node_trigger_mode_off):
                print('Unable to disable trigger mode (enum entry retrieval). Aborting...')
                return False

            node_trigger_mode.SetIntValue(node_trigger_mode_off.GetValue())

            print('Trigger mode disabled...')

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False

        return result


    def print_device_info(self, nodemap):
        """
        This function prints the device information of the camera from the transport
        layer; please see NodeMapInfo example for more in-depth comments on printing
        device information from the nodemap.

        :param nodemap: Transport layer device nodemap.
        :type nodemap: INodeMap
        :returns: True if successful, False otherwise.
        :rtype: bool
        """

        print('*** DEVICE INFORMATION ***\n')

        try:
            result = True
            node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

            if PySpin.IsReadable(node_device_information):
                features = node_device_information.GetFeatures()
                for feature in features:
                    node_feature = PySpin.CValuePtr(feature)
                    print('%s: %s' % (node_feature.GetName(),
                                    node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'))

            else:
                print('Device control information not readable.')

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False

        return result


    def run_single_camera(self, cam):
        """
        This function acts as the body of the example; please see NodeMapInfo example
        for more in-depth comments on setting up cameras.

        :param cam: Camera to run on.
        :type cam: CameraPtr
        :return: True if successful, False otherwise.
        :rtype: bool
        """
        try:
            result = True
            err = False

            # Retrieve TL device nodemap and print device information
            nodemap_tldevice = cam.GetTLDeviceNodeMap()

            result &= self.print_device_info(nodemap_tldevice)

            # Initialize camera
            cam.Init()

            # Retrieve GenICam nodemap
            nodemap = cam.GetNodeMap()

            # Configure trigger
            if self.configure_trigger(cam) is False:
                return False

            # Acquire images
            result &= self.acquire_images(cam, nodemap, nodemap_tldevice)

            # Reset trigger
            result &= self.reset_trigger(nodemap)

            # Deinitialize camera
            cam.DeInit()

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False

        return result


    def main(self):
        """
        Example entry point; please see Enumeration example for more in-depth
        comments on preparing and cleaning up the system.

        :return: True if successful, False otherwise.
        :rtype: bool
        """

        # Since this application saves images in the current folder
        # we must ensure that we have permission to write to this folder.
        # If we do not have permission, fail right away.
        try:
            test_file = open('test.txt', 'w+')
        except IOError:
            print('Unable to write to current directory. Please check permissions.')
            return False

        test_file.close()
        os.remove(test_file.name)

        result = True

        # Retrieve singleton reference to system object
        system:PySpin.SystemPtr = PySpin.System.GetInstance()

        # Get current library version
        version = system.GetLibraryVersion()
        print('Library version: %d.%d.%d.%d' % (version.major, version.minor, version.type, version.build))

        # Retrieve list of cameras from the system
        cam_list:PySpin.CameraList = system.GetCameras()

        num_cameras = cam_list.GetSize()

        print('Number of cameras detected: %d' % num_cameras)

        # Finish if there are no cameras
        if num_cameras == 0:
            # Clear camera list before releasing system
            cam_list.Clear()

            # Release system instance
            system.ReleaseInstance()

            print('Not enough cameras!')
            return False

        # Run example on each camera
        for i, cam in enumerate(cam_list):

            print('Running example for camera %d...' % i)

            result &= self.run_single_camera(cam)
            print('Camera %d example complete... \n' % i)
            break

        # Release reference to camera
        # NOTE: Unlike the C++ examples, we cannot rely on pointer objects being automatically
        # cleaned up when going out of scope.
        # The usage of del is preferred to assigning the variable to None.
        del cam

        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        MotTemp.main(self.trigPath, self.numImages, self.window, self.timeSplit)

        return result


if __name__ == '__main__':
    sys.exit(0)
