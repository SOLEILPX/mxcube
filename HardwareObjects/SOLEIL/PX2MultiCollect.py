from SOLEILMultiCollect import *
import shutil
import logging
from PyTango import DeviceProxy
import numpy
import re

class PX2MultiCollect(SOLEILMultiCollect):
    def __init__(self, name):

        SOLEILMultiCollect.__init__(self, name, LimaAdscDetector(), TunableEnergy())
        #SOLEILMultiCollect.__init__(self, name, DummyDetector(), TunableEnergy())
        self.motors = ['sampx', 'sampy', 'phiz', 'phiy']
        
    def init(self):

        logging.info("headername is %s" % self.headername )

        self.headerdev     = DeviceProxy( self.headername )
        self.mono1dev      = DeviceProxy( self.mono1name )
        self.det_mt_ts_dev = DeviceProxy( self.detmttsname )
        self.det_mt_tx_dev = DeviceProxy( self.detmttxname )
        self.det_mt_tz_dev = DeviceProxy( self.detmttzname )
        
        self.helical = False
        self.linear = False
        self.grid = False
        self.translational = False
        
        self._detector.prepareHeader = self.prepareHeader
        SOLEILMultiCollect.init(self)
       
    def prepareHeader(self):
        '''Will set up header given the actual values of beamline energy, mono and detector distance'''
        X, Y = self.beamCenter()

        BeamCenterX = str(round(X, 3))
        BeamCenterY = str(round(Y, 3))
        head = self.headerdev.read_attribute('header').value
        head = re.sub('BEAM_CENTER_X=\d\d\d\.\d', 'BEAM_CENTER_X=' + BeamCenterX, head)
        head = re.sub('BEAM_CENTER_Y=\d\d\d\.\d', 'BEAM_CENTER_Y=' + BeamCenterY, head)
        return head
    
    @task
    def move_motors(self, motor_position_dict, epsilon=0):
        logging.info("<PX2 MultiCollect> move_motors")
        for motor in motor_position_dict.keys(): #iteritems():
            position = motor_position_dict[motor]
            if isinstance(motor, str) or isinstance(motor, unicode):
                # find right motor object from motor role in diffractometer obj.
                motor_role = motor
                motor = self.bl_control.diffractometer.getDeviceByRole(motor_role)
                del motor_position_dict[motor_role]
                if motor is None:
                  continue
                motor_position_dict[motor]=position

            logging.getLogger("HWR").info("Moving motor '%s' to %f", motor.getMotorMnemonic(), position)
            motor.move(position, epsilon=epsilon, sync=True)

        while any([motor.motorIsMoving() for motor in motor_position_dict.iterkeys()]):
            logging.getLogger("HWR").info("Waiting for end of motors motion")
            time.sleep(0.1)  

    def beamCenter(self):
        '''Will calculate beam center coordinates'''

        # Useful values
        tz_ref = -6.5     # reference tz position for linear regression
        tx_ref = -17.0    # reference tx position for linear regression
        q = 0.102592  # pixel size in milimeters

        wavelength = self.mono1dev.read_attribute('lambda').value
        distance   = self.det_mt_ts_dev.read_attribute('position').value
        tx         = self.det_mt_tx_dev.read_attribute('position').value
        tz         = self.det_mt_tz_dev.read_attribute('position').value

        zcor = tz - tz_ref
        xcor = tx - tx_ref

        Theta = numpy.matrix([[1.55557116e+03,  1.43720063e+03],
                              [-8.51067454e-02, -1.84118001e-03],
                              [-1.99919592e-01,  3.57937064e+00]])  # values from 16.05.2013

        X = numpy.matrix([1., distance, wavelength])

        Origin = Theta.T * X.T
        Origin = Origin * q

        return Origin[1] + zcor, Origin[0] + xcor
        
    def set_helical(self, onmode, positions=None):
        logging.info("<PX2 MultiCollect> set helical")
        self.helical = onmode
        logging.info("<PX2 MultiCollect> set helical pos1 %s pos2 %s" % (positions['1'], positions['2']))
        self.helicalStart = positions['1']
        self.helicalFinal = positions['2']
        
    def set_translational(self, onmode, positions=None, step=None):
        logging.info("<PX2 MultiCollect> set translational")
        self.translational = onmode
        self.translationalStart = positions['1']
        self.translationalFinal = positions['2']
        if step is not None:
            self.translationalStep = step
        
    def set_linear(self, onmode, positions=None, step=None):
        logging.info("<PX2 MultiCollect> set linear")
        self.linear = onmode
        self.linearStart = positions['1']
        self.linearFinal = positions['2']
        if step is not None:
            self.linearStep = step
        
    def set_grid(self, onmode, positions=None):
        logging.info("<PX2 MultiCollect> set grid")
        self.grid = onmode

    def getPoints(self, start, final, nbSteps):
        logging.info("<PX2 MultiCollect> getPoints start %s, final %s" % (start, final))
        step = 1./ (nbSteps - 1)
        points = numpy.arange(0., 1.+(0.5*step), step)
        Positions = {}
        positions = []
        for motor in self.motors:
            scanRange = final[motor] - start[motor]
            Positions[motor] = start[motor] + points * scanRange
            positions.append(Positions[motor])
            
        positions = numpy.array(positions)
        return [dict(zip(self.motors, p)) for p in positions.T]
    
    def calculateHelicalCollectPositions(self, start, final, nImages):
        logging.info("<PX2 MultiCollect> calculateHelicalCollectPositions")
        positions = self.getPoints(start, final, nImages)
        return positions

    def calculateTranslationalCollectPositions(self, start, final, nImages):
        '''take into account the beam size and spread the positions optimally between start and final positions.'''
        logging.info("<PX2 MultiCollect> calculateTranslationalCollectPositions")
        positions = []
        horizontal_beam_size = self.get_horizontal_beam_size()
        totalHorizontalDistance = abs(final['phiy'] - start['phiy'])
        freeHorizontalSpace = totalHorizontalDistance - horizontal_beam_size
        # Due to our rotational axis being horizontal we take the horizontal beam size as the basic step size
        nPositions = int(freeHorizontalSpace // horizontal_beam_size) + 2
        nImagesPerPosition, remainder = divmod(nImages, nPositions)
        
        positions = self.getPoints(start, final, nPositions)
        explicit_positions = []
        k = 0
        for p in positions:
            k += 1
            to_add = [p] * (nImagesPerPosition)
            if k <= remainder:
                to_add += [p]
            explicit_positions += to_add
        return explicit_positions
    
    def getCollectPositions(self, nImages):
        logging.info("<PX2 MultiCollect> get collect positions")
        logging.info("getCollectPositions nImages %s" % nImages)
        positions = []
        if self.helical:
            start, final = self.helicalStart, self.helicalFinal
            positions = self.calculateHelicalCollectPositions(start, final, nImages)
            self.helical = False
        elif self.translational:
            start, final = self.translationalStart, self.translationalFinal
            positions = self.calculateTranslationalCollectPositions(start, final, nImages)
            self.translational = False
        elif self.linear:
            start, final = self.linearStart, self.linearFinal
            positions = self.getPoints(start, final, nImages)
            self.linear = False
        elif self.grid:
            positions = self.calculateGridPositions(self.grid_start, self.grid_nbsteps, self.grid_lengths)
            self.grid = False
        else:
            positions = [{} for k in range(nImages)]
        return positions
        
    def newWedge(self, imageNums, ScanStartAngle, template, positions):
        return {'imageNumbers': imageNums, 
                'startAtAngle': ScanStartAngle, 
                'template': template, 
                'positions': positions}
    
    def prepareWedges(self, firstImage, 
                            nbFrames, 
                            ScanStartAngle, 
                            ScanRange, 
                            wedgeSize, 
                            inverse, 
                            ScanOverlap, 
                            template):
        '''Based on collect parameters will prepare all the wedges to be collected.'''
        logging.info('Preparing wedges')
        search_template = template.lower()
        if self.helical:
            if 'transl' in search_template:
                self.helical = False
                self.translational = True
                self.translationalStart, self.translationalFinal = self.helicalStart, self.helicalFinal
            elif 'linear' in search_template:
                self.helical = False
                self.linear = True
                self.linearStart, self.linearFinal = self.helicalStart, self.helicalFinal
            else:
                pass
        wedges = []
        
        imageNums = range(firstImage, nbFrames + firstImage)
        positions = self.getCollectPositions(nbFrames)
        
        wedges = self.newWedge(imageNums, ScanStartAngle, template, positions)
        if inverse is True:
            inv_wedge = self.newWedge(imageNums, ScanStartAngle, template_inv, positions)
            wedgeSize = int(reference_interval)
            numberOfFullWedges, lastWedgeSize = divmod(nbFrames, wedgeSize)
            for k in range(0, numberOfFullWedges):
                start = k * numberOfFullWedges
                stop = (k+1) * numberOfFullWedges
                wedges.append(wedge[start: stop] + inv_wedge[start: stop])
            wedges.append(wedge[stop:] + inv_wedge[stop:])
        print 'Wedges to collect:'
        print wedges
        logging.info('Wedges to collect %s' % wedges)
        return wedges
           

    @task
    def do_collect(self, owner, data_collect_parameters, in_multicollect=False):
        # reset collection id on each data collect
        logging.info("<SOLEIL do_collect>  data_collect_parameters %s" % data_collect_parameters)
        self.collection_id = None

        # Preparing directory path for images and processing files
        # creating image file template and jpegs files templates
        file_parameters = data_collect_parameters["fileinfo"]

        file_parameters["suffix"] = self.bl_config.detector_fileext
        image_file_template = "%(prefix)s_%(run_number)s_%%04d.%(suffix)s" % file_parameters
        file_parameters["template"] = image_file_template

        archive_directory = self.get_archive_directory(file_parameters["directory"])
        data_collect_parameters["archive_dir"] = archive_directory

        if archive_directory:
            jpeg_filename="%s.jpeg" % os.path.splitext(image_file_template)[0]
            thumb_filename="%s.thumb.jpeg" % os.path.splitext(image_file_template)[0]
            jpeg_file_template = os.path.join(archive_directory, jpeg_filename)
            jpeg_thumbnail_file_template = os.path.join(archive_directory, thumb_filename)
        else:
            jpeg_file_template = None
            jpeg_thumbnail_file_template = None
        # database filling
        logging.info("<AbstractMultiCollect> - LIMS is %s" % str(self.bl_control.lims))
        if self.bl_control.lims:
            data_collect_parameters["collection_start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if self.bl_control.machine_current is not None:
                data_collect_parameters["synchrotronMode"] = self.get_machine_fill_mode()
            data_collect_parameters["status"] = "failed"

            (self.collection_id, detector_id) = \
                                 self.bl_control.lims.store_data_collection(data_collect_parameters, self.bl_config)
              
            data_collect_parameters['collection_id'] = self.collection_id

            if detector_id:
                data_collect_parameters['detector_id'] = detector_id
              
        # Creating the directory for images and processing information
        self.create_directories(file_parameters['directory'],  file_parameters['process_directory'])
        self.xds_directory, self.mosflm_directory = self.prepare_input_files(file_parameters["directory"], file_parameters["prefix"], file_parameters["run_number"], file_parameters['process_directory'])
        data_collect_parameters['xds_dir'] = self.xds_directory

        sample_id, sample_location, sample_code = self.get_sample_info_from_parameters(data_collect_parameters)
        data_collect_parameters['blSampleId'] = sample_id

        if self.bl_control.sample_changer is not None:
            data_collect_parameters["actualSampleBarcode"] = \
                self.bl_control.sample_changer.getLoadedSampleDataMatrix()
            data_collect_parameters["actualContainerBarcode"] = \
                self.bl_control.sample_changer.currentBasketDataMatrix

            basket, vial = (self.bl_control.sample_changer.currentBasket,
                        self.bl_control.sample_changer.currentSample)

            data_collect_parameters["actualSampleSlotInContainer"] = vial
            data_collect_parameters["actualContainerSlotInSC"] = basket

        else:
            data_collect_parameters["actualSampleBarcode"] = None
            data_collect_parameters["actualContainerBarcode"] = None

        try:
            # why .get() is not working as expected?
            # got KeyError anyway!
            if data_collect_parameters["take_snapshots"]:
              self.take_crystal_snapshots()
        except KeyError:
            pass

        centring_info = {}
        try:
            centring_status = self.diffractometer().getCentringStatus()
        except:
            pass
        else:
            centring_info = dict(centring_status)

        #Save sample centring positions
        motors = centring_info.get("motors", {})
        logging.info('do_collect motors %s' % motors)
        extra_motors = centring_info.get("extraMotors", {})

        positions_str = ""

        motors_to_move_before_collect = data_collect_parameters.setdefault("motors", {})
        
        for motor in motors:
          positions_str = "%s %s=%f" % (positions_str, motor, motors[motor])
          # update 'motors' field, so diffractometer will move to centring pos.
          motors_to_move_before_collect.update({motor: motors[motor]})
        for motor in extra_motors:
          positions_str = "%s %s=%f" % (positions_str, motor, extra_motors[motor])
          motors_to_move_before_collect.update({motor: extra_motors[motor]})
          
        data_collect_parameters['actualCenteringPosition'] = positions_str

        if self.bl_control.lims:
          try:
            if self.current_lims_sample:
              self.current_lims_sample['lastKnownCentringPosition'] = positions_str
              self.bl_control.lims.update_bl_sample(self.current_lims_sample)
          except:
            logging.getLogger("HWR").exception("Could not update sample infromation in LIMS")

        if 'images' in centring_info:
          # Save snapshots
          snapshot_directory = self.get_archive_directory(file_parameters["directory"])
          logging.getLogger("HWR").debug("Snapshot directory is %s" % snapshot_directory)

          try:
            self.create_directories(snapshot_directory)
          except:
              logging.getLogger("HWR").exception("Error creating snapshot directory")
          else:
              snapshot_i = 1
              snapshots = []
              for img in centring_info["images"]:
                img_phi_pos = img[0]
                img_data = img[1]
                snapshot_filename = "%s_%s_%s.snapshot.jpeg" % (file_parameters["prefix"],
                                                                file_parameters["run_number"],
                                                                snapshot_i)
                full_snapshot = os.path.join(snapshot_directory,
                                             snapshot_filename)

                try:
                  f = open(full_snapshot, "w")
                  f.write(img_data)
                except:
                  logging.getLogger("HWR").exception("Could not save snapshot!")
                  try:
                    f.close()
                  except:
                    pass

                data_collect_parameters['xtalSnapshotFullPath%i' % snapshot_i] = full_snapshot

                snapshots.append(full_snapshot)
                snapshot_i+=1

          try:
            data_collect_parameters["centeringMethod"] = centring_info['method']
          except:
            data_collect_parameters["centeringMethod"] = None

        if self.bl_control.lims:
            try:
                self.bl_control.lims.update_data_collection(data_collect_parameters)
            except:
                logging.getLogger("HWR").exception("Could not update data collection in LIMS")
        #import pdb;pdb.set_trace()
        oscillation_parameters = data_collect_parameters["oscillation_sequence"][0]
        sample_id = data_collect_parameters['blSampleId']
        inverse_beam = "reference_interval" in oscillation_parameters
        reference_interval = oscillation_parameters.get("reference_interval", 1)
        
        firstImage = oscillation_parameters["start_image_number"] 
        nbFrames = oscillation_parameters["number_of_images"]
        ScanStartAngle = oscillation_parameters["start"]
        ScanRange = oscillation_parameters["range"]
        wedgeSize = reference_interval
        inverse = inverse_beam
        ScanOverlap = oscillation_parameters["overlap"]
        template = image_file_template
        myWedges = self.prepareWedges(firstImage, 
                                      nbFrames, 
                                      ScanStartAngle, 
                                      ScanRange, 
                                      wedgeSize, 
                                      inverse, 
                                      ScanOverlap, 
                                      template)
        positions = myWedges['positions']
        wedges_to_collect = self.prepare_wedges_to_collect(oscillation_parameters["start"],
                                                           oscillation_parameters["number_of_images"],
                                                           oscillation_parameters["range"],
                                                           reference_interval,
                                                           inverse_beam,
                                                           oscillation_parameters["overlap"])
        logging.info('do_collect wedges_to_collect %s' % wedges_to_collect)
        nframes = len(wedges_to_collect)
        self.emit("collectNumberOfFrames", nframes) 

        start_image_number = oscillation_parameters["start_image_number"]    
        if data_collect_parameters["skip_images"]:
            for start, wedge_size in wedges_to_collect[:]:
              filename = image_file_template % start_image_number
              file_location = file_parameters["directory"]
              file_path  = os.path.join(file_location, filename)
              if os.path.isfile(file_path):
                logging.info("Skipping existing image %s", file_path)
                del wedges_to_collect[0]
                start_image_number += 1
                nframes -= 1
              else:
                # images have to be consecutive
                break

        if nframes == 0:
            return
            
        # write back to the dictionary to make macros happy... TODO: remove this once macros are removed!
        oscillation_parameters["start_image_number"] = start_image_number
        oscillation_parameters["number_of_images"] = nframes
        data_collect_parameters["skip_images"] = 0
 
        # data collection
        self.data_collection_hook(data_collect_parameters)
        
        if 'transmission' in data_collect_parameters:
          self.set_transmission(data_collect_parameters["transmission"])

        if 'wavelength' in data_collect_parameters:
          self.set_wavelength(data_collect_parameters["wavelength"])
        elif 'energy' in data_collect_parameters:
          self.set_energy(data_collect_parameters["energy"])
        
        if 'resolution' in data_collect_parameters:
          resolution = data_collect_parameters["resolution"]["upper"]
          self.set_resolution(resolution)
        elif 'detdistance' in oscillation_parameters:
          self.move_detector(oscillation_parameters["detdistance"])
          
        self.close_fast_shutter()

        self.move_motors(motors_to_move_before_collect)

        with cleanup(self.data_collection_cleanup):
            self.open_safety_shutter(timeout=10)

            self.prepare_intensity_monitors()
           
            frame = start_image_number
            osc_range = oscillation_parameters["range"]
            exptime = oscillation_parameters["exposure_time"]
            npass = oscillation_parameters["number_of_passes"]

            # update LIMS
            if self.bl_control.lims:
                  try:
                    data_collect_parameters["flux"] = self.get_flux()
                    data_collect_parameters["flux_end"] = data_collect_parameters["flux"]
                    data_collect_parameters["wavelength"]= self.get_wavelength()
                    data_collect_parameters["detectorDistance"] =  self.get_detector_distance()
                    data_collect_parameters["resolution"] = self.get_resolution()
                    data_collect_parameters["transmission"] = self.get_transmission()
                    gap1, gap2, gap3 = self.get_undulators_gaps()
                    data_collect_parameters["undulatorGap1"] = gap1
                    data_collect_parameters["undulatorGap2"] = gap2
                    data_collect_parameters["undulatorGap3"] = gap3
                    data_collect_parameters["resolutionAtCorner"] = self.get_resolution_at_corner()
                    beam_size_x, beam_size_y = self.get_beam_size()
                    data_collect_parameters["beamSizeAtSampleX"] = beam_size_x
                    data_collect_parameters["beamSizeAtSampleY"] = beam_size_y
                    data_collect_parameters["beamShape"] = self.get_beam_shape()
                    hor_gap, vert_gap = self.get_slit_gaps()
                    data_collect_parameters["slitGapHorizontal"] = hor_gap
                    data_collect_parameters["slitGapVertical"] = vert_gap
                    beam_centre_x, beam_centre_y = self.get_beam_centre()
                    data_collect_parameters["xBeam"] = beam_centre_x
                    data_collect_parameters["yBeam"] = beam_centre_y

                    logging.info("Updating data collection in ISPyB")
                    self.bl_control.lims.update_data_collection(data_collect_parameters, wait=True)
                    logging.info("Done")
                  except:
                    logging.getLogger("HWR").exception("Could not store data collection into LIMS")

            if self.bl_control.lims and self.bl_config.input_files_server:
                self.write_input_files(self.collection_id, wait=False) 

            self.prepare_acquisition(1 if data_collect_parameters.get("dark", 0) else 0,
                                     wedges_to_collect[0][0],
                                     osc_range,
                                     exptime,
                                     npass,
                                     nframes,
                                     data_collect_parameters["comment"])
            data_collect_parameters["dark"] = 0

            # at this point input files should have been written           
            if self.bl_control.lims and self.bl_config.input_files_server:
              if data_collect_parameters.get("processing", False)=="True":
                self.trigger_auto_processing("before",
                                       self.xds_directory,
                                       data_collect_parameters["EDNA_files_dir"],
                                       data_collect_parameters["anomalous"],
                                       data_collect_parameters["residues"],
                                       inverse_beam,
                                       data_collect_parameters["do_inducedraddam"],
                                       in_multicollect,
                                       data_collect_parameters.get("sample_reference", {}).get("spacegroup", ""),
                                       data_collect_parameters.get("sample_reference", {}).get("cell", ""))
            
            k = 0
            reference_position = positions[0]
            for start, wedge_size in wedges_to_collect:
                k += 1
                end = start + osc_range
                collect_position = positions[k-1]
                filename = image_file_template % frame
                try:
                  jpeg_full_path = jpeg_file_template % frame
                  jpeg_thumbnail_full_path = jpeg_thumbnail_file_template % frame
                except:
                  jpeg_full_path = None
                  jpeg_thumbnail_full_path = None
                file_location = file_parameters["directory"]
                file_path  = os.path.join(file_location, filename)
                
                logging.info("Frame %d, %7.3f to %7.3f degrees", frame, start, end)

                self.set_detector_filenames(frame, start, file_path, jpeg_full_path, jpeg_thumbnail_full_path)
                
                osc_start, osc_end = self.prepare_oscillation(start, osc_range, exptime, npass)
                
                with error_cleanup(self.reset_detector):
                    self.move_motors(collect_position, epsilon=0.0002)
                    self.start_acquisition(exptime, npass, frame==start_image_number)
                    if osc_end - osc_start < 1E-4:
                       self.open_fast_shutter()
                       time.sleep(exptime)
                       self.close_fast_shutter()
                    else:
                       self.do_oscillation(osc_start, osc_end, exptime, npass)
                    self.stop_acquisition()
                    last_frame = start_image_number + nframes - 1
                    self.write_image(frame == last_frame)
                    
                    # Store image in lims
                    if self.bl_control.lims:
                      if self.store_image_in_lims(frame, frame == start_image_number, frame == last_frame):
                        lims_image={'dataCollectionId': self.collection_id,
                                    'fileName': filename,
                                    'fileLocation': file_location,
                                    'imageNumber': frame,
                                    'measuredIntensity': self.get_measured_intensity(),
                                    'synchrotronCurrent': self.get_machine_current(),
                                    'machineMessage': self.get_machine_message(),
                                    'temperature': self.get_cryo_temperature()}

                        if archive_directory:
                          lims_image['jpegFileFullPath'] = jpeg_full_path
                          lims_image['jpegThumbnailFileFullPath'] = jpeg_thumbnail_full_path

                        try:
                          self.bl_control.lims.store_image(lims_image)
                        except:
                          logging.getLogger("HWR").exception("Could not store store image in LIMS")
                                              
                    self.emit("collectImageTaken", frame)
                        
                    if self.bl_control.lims and self.bl_config.input_files_server:
                      if data_collect_parameters.get("processing", False)=="True":
                         self.trigger_auto_processing("image",
                                                   self.xds_directory, 
                                                   data_collect_parameters["EDNA_files_dir"],
                                                   data_collect_parameters["anomalous"],
                                                   data_collect_parameters["residues"],
                                                   inverse_beam,
                                                   data_collect_parameters["do_inducedraddam"],
                                                   in_multicollect,
                                                   data_collect_parameters.get("sample_reference", {}).get("spacegroup", ""),
                                                   data_collect_parameters.get("sample_reference", {}).get("cell", ""))
                frame += 1

            self.finalize_acquisition()

