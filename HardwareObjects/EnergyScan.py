# -*- coding: utf-8 -*-
from qt import *
from HardwareRepository.BaseHardwareObjects import Equipment
from HardwareRepository.TaskUtils import *
import logging
import PyChooch
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
#from SpecClient import SpecClientError
#from SpecClient import SpecVariable
#from SpecClient import SpecConnectionsManager
#from SpecClient import SpecEventsDispatcher
#from SimpleDevice2c import SimpleDevice #MS 05.03.2013
import os
import time
import types
import math
from xabs_lib import *
#from simple_scan_class import *
import string
#MS 05.03.2013
from PyTango import DeviceProxy
import numpy
import pickle

class EnergyScan(Equipment):
    
    MANDATORY_HO={"BLEnergy":"BLEnergy"}
    
    
    def init(self):
        self.scanning = None
        self.moving = None
        self.energyMotor = None
        self.energyScanArgs = None
        self.archive_prefix = None
        self.energy2WavelengthConstant=None
        self.defaultWavelength=None
        self._element = None
        self._edge = None
        try:
            self.defaultWavelengthChannel=self.getChannelObject('default_wavelength')
        except KeyError:
            self.defaultWavelengthChannel=None
        else:
            self.defaultWavelengthChannel.connectSignal("connected", self.sConnected) 
            self.defaultWavelengthChannel.connectSignal("disconnected", self.sDisconnected)

        if self.defaultWavelengthChannel is None:
            #MAD beamline
            try:
                self.energyScanArgs=self.getChannelObject('escan_args')
            except KeyError:
                logging.getLogger("HWR").warning('EnergyScan: error initializing energy scan arguments (missing channel)')
                self.energyScanArgs=None

            try:
                self.scanStatusMessage=self.getChannelObject('scanStatusMsg')
            except KeyError:
                self.scanStatusMessage=None
                logging.getLogger("HWR").warning('EnergyScan: energy messages will not appear (missing channel)')
            else:
                self.connect(self.scanStatusMessage,'update',self.scanStatusChanged)

            try:
                self.doEnergyScan.connectSignal('commandReplyArrived', self.scanCommandFinished)
                self.doEnergyScan.connectSignal('commandBeginWaitReply', self.scanCommandStarted)
                self.doEnergyScan.connectSignal('commandFailed', self.scanCommandFailed)
                self.doEnergyScan.connectSignal('commandAborted', self.scanCommandAborted)
                self.doEnergyScan.connectSignal('commandReady', self.scanCommandReady)
                self.doEnergyScan.connectSignal('commandNotReady', self.scanCommandNotReady)
            except AttributeError,diag:
                logging.getLogger("HWR").warning('EnergyScan: error initializing energy scan (%s)' % str(diag))
                self.doEnergyScan=None
            else:
                self.doEnergyScan.connectSignal("connected", self.sConnected)
                self.doEnergyScan.connectSignal("disconnected", self.sDisconnected)

            self.energyMotor=self.getObjectByRole("energy")
            self.resolutionMotor=self.getObjectByRole("resolution")
            self.previousResolution=None
            self.lastResolution=None

            self.dbConnection=self.getObjectByRole("dbserver")
            if self.dbConnection is None:
                logging.getLogger("HWR").warning('EnergyScan: you should specify the database hardware object')
            self.scanInfo=None

            self.transmissionHO=self.getObjectByRole("transmission")
            if self.transmissionHO is None:
                logging.getLogger("HWR").warning('EnergyScan: you should specify the transmission hardware object')

        self.dbConnection=self.getObjectByRole("dbserver")
        if self.dbConnection is None:
            logging.getLogger("HWR").warning('EnergyScan: you should specify the database hardware object')
        self.scanInfo=None

        if self.isSpecConnected():
            self.sConnected()
            
    def connectTangoDevices(self):
        try :
            self.BLEnergydevice = DeviceProxy(self.getProperty("blenergy")) #, verbose=False)
            self.BLEnergydevice.waitMoves = True
            self.BLEnergydevice.timeout = 30000
        except :
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("blenergy")))
            self.canScan = False
            
        # Connect to device mono defined "tangoname2" in the xml file 
        # used for conversion in wavelength
        try :    
            self.monodevice = DeviceProxy(self.getProperty("mono")) #, verbose=False)
            self.monodevice.waitMoves = True
            self.monodevice.timeout = 6000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("mono")))
            self.canScan = False
        #mono_mt_rx
        try :    
            self.mono_mt_rx_device = DeviceProxy(self.getProperty("mono_mt_rx")) #, verbose=False)
            #self.monodevice.waitMoves = True
            self.mono_mt_rx_device.timeout = 6000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("mono_mt_rx")))
            self.canScan = False
        # Nom du device bivu (Energy to gap) : necessaire pour amelioration du positionnement de l'onduleur (Backlash)
        try :    
            self.U20Energydevice = DeviceProxy(self.getProperty("U24Energy")) #, movingState="MOVING")
            self.U20Energydevice.timeout = 30000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("U24Energy")))
            self.canScan = False
            
        try :
            self.fluodetdevice = DeviceProxy(self.getProperty("ketek")) #, verbose=False)
            self.fluodetdevice.timeout = 1000
        except :
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("ketek")))
            self.canScan = False
            
        try :    
            self.counterdevice = DeviceProxy(self.getProperty("counter")) #, verbose=False)
            self.counterdevice.timeout = 1000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("counter")))
            self.canScan = False

        try :    
            self.xbpmdevice = DeviceProxy(self.getProperty("xbpm")) #, verbose=False)
            self.xbpmdevice.timeout = 30000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("xbpm")))
            self.canScan = False
       
        try :    
            self.attdevice = DeviceProxy(self.getProperty("attenuator")) #, verbose=False)
            self.attdevice.timeout = 6000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("attenuator")))
            self.canScan = False
        
#        try :    
#            self.md2device = DeviceProxy(self.getProperty("md2")) #, verbose=False)
#            self.md2device.timeout = 2000
#        except :    
#            logging.getLogger("HWR").error("%s not found" %(self.getProperty("md2")))
#            self.canScan = False
        
        try:
            self.lightdevice = DeviceProxy(self.getProperty("lightextract")) #, verbose=False)
            self.lightdevice.timeout = 2000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("lightextract")))
            self.canScan = False

        try:
            self.guillotdevice = DeviceProxy(self.getProperty("guillot")) #, verbose=False)
            self.guillotdevice.timeout = 2000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("guillot")))
            self.canScan = False

        try:
            self.bstdevice = DeviceProxy(self.getProperty("bst")) #, verbose=False)
            self.bstdevice.timeout = 2000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("bst")))
            self.canScan = False

        try:
            self.ketekinsertdevice = DeviceProxy(self.getProperty("ketekinsert")) #, verbose=False)
            self.ketekinsertdevice.timeout = 2000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("ketekinsert")))
            self.canScan = False

        try:
            self.fastshutterdevice = DeviceProxy(self.getProperty("fastshutter")) #, verbose=False)
            self.fastshutterdevice.timeout = 2000
        except :    
            logging.getLogger("HWR").error("%s not found" %(self.getProperty("fastshutter")))
            self.canScan = False
        
                            
    def isConnected(self):
	return True
        #return self.isSpecConnected()
        
    def isSpecConnected(self):
        logging.getLogger("HWR").debug('EnergyScan:isSpecConnected')
        return True

    # Handler for spec connection
    def sConnected(self):
        logging.getLogger("HWR").debug('EnergyScan:sConnected')
        self.emit('connected', ())
        self.emit('setDirectory', (self.directoryPrefix,))


    # Handler for spec disconnection
    def sDisconnected(self):
        logging.getLogger("HWR").debug('EnergyScan:sDisconnected')
        self.emit('disconnected', ())

    # Energy scan commands
    def canScanEnergy(self):
	return True
        logging.getLogger("HWR").debug('EnergyScan:canScanEnergy : %s' %(str(self.canScan)))
        return self.canScan

 
#        return self.doEnergyScan is not None
	
    def startEnergyScan(self, 
                        element, 
                        edge, 
                        directory, 
                        prefix, 
                        session_id = None, 
                        blsample_id = None):
        
        logging.getLogger("HWR").debug('EnergyScan:startEnergyScan')
        print 'edge', edge
        print 'element', element
        print 'directory', directory
        print 'prefix', prefix
        #logging.getLogger("HWR").debug('EnergyScan:edge', edge)
        #logging.getLogger("HWR").debug('EnergyScan:element', element)
        #logging.getLogger("HWR").debug('EnergyScan:directory', directory)
        #logging.getLogger("HWR").debug('EnergyScan:prefix', prefix)
        #logging.getLogger("HWR").debug('EnergyScan:edge', edge)
        self.scanInfo={"sessionId":session_id,
                       "blSampleId":blsample_id,
                       "element":element,
                       "edgeEnergy":edge}
#        if self.fluodetectorHO is not None:
#            self.scanInfo['fluorescenceDetector']=self.fluodetectorHO.userName()
        if not os.path.isdir(directory):
            logging.getLogger("HWR").debug("EnergyScan: creating directory %s" % directory)
            try:
                os.makedirs(directory)
            except OSError,diag:
                logging.getLogger("HWR").error("EnergyScan: error creating directory %s (%s)" % (directory,str(diag)))
                self.emit('scanStatusChanged', ("Error creating directory",))
                return False
        self.doEnergyScan(element, edge, directory, prefix)
        return True
        
    def cancelEnergyScan(self):
        logging.getLogger("HWR").debug('EnergyScan:cancelEnergyScan')
        if self.scanning:
            self.scanning = False
            
    def scanCommandReady(self):
        logging.getLogger("HWR").debug('EnergyScan:scanCommandReady')
        if not self.scanning:
            self.emit('energyScanReady', (True,))
            
    def scanCommandNotReady(self):
        logging.getLogger("HWR").debug('EnergyScan:scanCommandNotReady')
        if not self.scanning:
            self.emit('energyScanReady', (False,))
            
    def scanCommandStarted(self):
        logging.getLogger("HWR").debug('EnergyScan:scanCommandStarted')

        self.scanInfo['startTime']=time.strftime("%Y-%m-%d %H:%M:%S")
        self.scanning = True
        self.emit('energyScanStarted', ())
    
    def scanCommandFailed(self):
        logging.getLogger("HWR").debug('EnergyScan:scanCommandFailed')
        self.scanInfo['endTime']=time.strftime("%Y-%m-%d %H:%M:%S")
        self.scanning = False
        self.storeEnergyScan()
        self.emit('energyScanFailed', ())
        self.ready_event.set()
    def scanCommandAborted(self, *args):
        self.emit('energyScanFailed', ())
        self.ready_event.set()
    def scanCommandFinished(self,result, *args):
        with cleanup(self.ready_event.set):
            self.scanInfo['endTime']=time.strftime("%Y-%m-%d %H:%M:%S")
            logging.getLogger("HWR").debug("EnergyScan: energy scan result is %s" % result)
            self.scanning = False
            if result==-1:
                self.storeEnergyScan()
                self.emit('energyScanFailed', ())
                return

            try:
              t = float(result["transmissionFactor"])
            except:
              pass
            else:
              self.scanInfo["transmissionFactor"]=t
            try:
                et=float(result['exposureTime'])
            except:
                pass
            else:
                self.scanInfo["exposureTime"]=et
            try:
                se=float(result['startEnergy'])
            except:
                pass
            else:
                self.scanInfo["startEnergy"]=se
            try:
                ee=float(result['endEnergy'])
            except:
                pass
            else:
                self.scanInfo["endEnergy"]=ee

            try:
                bsX=float(result['beamSizeHorizontal'])
            except:
                pass
            else:
                self.scanInfo["beamSizeHorizontal"]=bsX

            try:
                bsY=float(result['beamSizeVertical'])
            except:
                pass
            else:
                self.scanInfo["beamSizeVertical"]=bsY

            try:
                self.thEdge=float(result['theoreticalEdge'])/1000.0
            except:
                pass

            self.emit('energyScanFinished', (self.scanInfo,))


    def doChooch(self, scanObject, elt, edge, scanArchiveFilePrefix, scanFilePrefix):
        symbol = "_".join((elt, edge))
        scanArchiveFilePrefix = "_".join((scanArchiveFilePrefix, symbol))

        i = 1
        while os.path.isfile(os.path.extsep.join((scanArchiveFilePrefix + str(i), "raw"))):
            i = i + 1

        scanArchiveFilePrefix = scanArchiveFilePrefix + str(i) 
        archiveRawScanFile=os.path.extsep.join((scanArchiveFilePrefix, "raw"))
        rawScanFile=os.path.extsep.join((scanFilePrefix, "raw"))
        scanFile=os.path.extsep.join((scanFilePrefix, "efs"))

        if not os.path.exists(os.path.dirname(scanArchiveFilePrefix)):
            os.makedirs(os.path.dirname(scanArchiveFilePrefix))
        
        try:
            pk, fppPeak, fpPeak, ip, fppInfl, fpInfl, chooch_graph_data = PyChooch.calc(scanData,
                                                                                    elt, 
                                                                                    edge, 
                                                                                    filenameOut)
        except:
            pk = self.thEdge
            rm = (pk + 50.) / 1000.0
            savpk = pk
            ip = pk - 5. / 1000.0
            logging.getLogger("HWR").info("Chooch failed badly")
            #, fppPeak, fpPeak, ip, fppInfl, fpInfl, chooch_graph_data = self.thEdge, 
            
            if scanObject is None:                
                raw_data_file = os.path.join(os.path.dirname(scanFilePrefix), 'data.raw')
                try:
                    raw_file = open(raw_data_file, 'r')
                except:
                    self.storeEnergyScan()
                    self.emit("energyScanFailed", ())
                    return
                
                for line in raw_file.readlines()[2:]:
                    (x, y) = line.split('\t')
                    x = float(x.strip())
                    y = float(y.strip())
                    x = x < 1000 and x*1000.0 or x
                    scanData.append((x, y))
                    f.write("%f,%f\r\n" % (x, y))
                    pyarch_f.write("%f,%f\r\n"% (x, y))
            else:
                for i in range(len(scanObject.x)):
                    x = float(scanObject.x[i])
                    x = x < 1000 and x*1000.0 or x 
                    y = float(scanObject.y[i])
                    scanData.append((x, y))
                    f.write("%f,%f\r\n" % (x, y))
                    pyarch_f.write("%f,%f\r\n"% (x, y)) 

            f.close()
            pyarch_f.close()
            self.scanInfo["scanFileFullPath"]=str(archiveRawScanFile)

        pk, fppPeak, fpPeak, ip, fppInfl, fpInfl, chooch_graph_data = PyChooch.calc(scanData, elt, edge, scanFile)
        rm=(pk+30)/1000.0
        pk=pk/1000.0
        savpk = pk
        ip = ip / 1000.0
        comm = ""
        logging.getLogger("HWR").info("th. Edge %s ; chooch results are pk=%f, ip=%f, rm=%f" % (self.thEdge,  pk, ip, rm))

        if math.fabs(self.thEdge - ip) > 0.01:
            pk = 0
            ip = 0
            rm = self.thEdge + 0.05
            comm = 'Calculated peak (%f) is more that 10eV away from the theoretical value (%f). Please check your scan' % (savpk, self.thEdge)
    
            logging.getLogger("HWR").warning('EnergyScan: calculated peak (%f) is more that 10eV %s the theoretical value (%f). Please check your scan and choose the energies manually' % (savpk, (self.thEdge - ip) > 0.01 and "below" or "above", self.thEdge))
        
        scanFile = filenameIn
        archiveEfsFile = filenameOut #os.path.extsep.join((scanArchiveFilePrefix, "efs"))
        try:
            fi = open(scanFile)
            fo = open(archiveEfsFile, "w")
        except:
            self.storeEnergyScan()
            self.emit("energyScanFailed", ())
            return
        else:
            fo.write(fi.read())
            fi.close()
            fo.close()

        self.scanInfo["peakEnergy"]=pk
        self.scanInfo["inflectionEnergy"]=ip
        self.scanInfo["remoteEnergy"]=rm
        self.scanInfo["peakFPrime"]=fpPeak
        self.scanInfo["peakFDoublePrime"]=fppPeak
        self.scanInfo["inflectionFPrime"]=fpInfl
        self.scanInfo["inflectionFDoublePrime"]=fppInfl
        self.scanInfo["comments"] = comm

        chooch_graph_x, chooch_graph_y1, chooch_graph_y2 = zip(*chooch_graph_data)
        chooch_graph_x = list(chooch_graph_x)
        for i in range(len(chooch_graph_x)):
          chooch_graph_x[i]=chooch_graph_x[i]/1000.0

        logging.getLogger("HWR").info("<chooch> Saving png" )
        # prepare to save png files
        title="%10s  %6s  %6s\n%10s  %6.2f  %6.2f\n%10s  %6.2f  %6.2f" % ("energy", "f'", "f''", pk, fpPeak, fppPeak, ip, fpInfl, fppInfl) 
        fig=Figure(figsize=(15, 11))
        ax=fig.add_subplot(211)
        ax.set_title("%s\n%s" % (scanFile, title))
        ax.grid(True)
        ax.plot(*(zip(*scanData)), **{"color":'black'})
        ax.set_xlabel("Energy")
        ax.set_ylabel("MCA counts")
        ax2=fig.add_subplot(212)
        ax2.grid(True)
        ax2.set_xlabel("Energy")
        ax2.set_ylabel("")
        handles = []
        handles.append(ax2.plot(chooch_graph_x, chooch_graph_y1, color='blue'))
        handles.append(ax2.plot(chooch_graph_x, chooch_graph_y2, color='red'))
        canvas=FigureCanvasAgg(fig)

        escan_png = filenameOut[:-3] + 'png' #.replace('.esf', '.png') #os.path.extsep.join((scanFilePrefix, "png"))
        escan_archivepng = filenameOut[:-4] + '_archive.png'  #os.path.extsep.join((scanArchiveFilePrefix, "png")) 
        self.scanInfo["jpegChoochFileFullPath"]=str(escan_archivepng)
        try:
            logging.getLogger("HWR").info("Rendering energy scan and Chooch graphs to PNG file : %s", escan_png)
            canvas.print_figure(escan_png, dpi=80)
        except:
            logging.getLogger("HWR").exception("could not print figure")
        try:
            logging.getLogger("HWR").info("Saving energy scan to archive directory for ISPyB : %s", escan_archivepng)
            canvas.print_figure(escan_archivepng, dpi=80)
        except:
            logging.getLogger("HWR").exception("could not save figure")

        self.storeEnergyScan()
        self.scanInfo=None

        logging.getLogger("HWR").info("<chooch> returning" )
        return pk, fppPeak, fpPeak, ip, fppInfl, fpInfl, rm, chooch_graph_x, chooch_graph_y1, chooch_graph_y2, title
    
    def scanStatusChanged(self,status):
        logging.getLogger("HWR").debug('EnergyScan:scanStatusChanged')
        self.emit('scanStatusChanged', (status,))
        
    def storeEnergyScan(self):
        if self.dbConnection is None:
            return
        try:
            session_id=int(self.scanInfo['sessionId'])
        except:
            return
        gevent.spawn(StoreEnergyScanThread, self.dbConnection,self.scanInfo)
        #self.storeScanThread.start()

    def updateEnergyScan(self,scan_id,jpeg_scan_filename):
        pass

    # Move energy commands
    def canMoveEnergy(self):
        return self.canScanEnergy()
    
    def getCurrentEnergy(self):
        if self.energyMotor is not None:
            try:
                return self.energyMotor.getPosition()
            except: 
                logging.getLogger("HWR").exception("EnergyScan: couldn't read energy")
                return None
        elif self.energy2WavelengthConstant is not None and self.defaultWavelength is not None:
            return self.energy2wavelength(self.defaultWavelength)
        return None


    def get_value(self):
        return self.getCurrentEnergy()
    
    
    def getEnergyLimits(self):
        lims=None
        if self.energyMotor is not None:
            if self.energyMotor.isReady():
                lims=self.energyMotor.getLimits()
        return lims
    def getCurrentWavelength(self):
        if self.energyMotor is not None:
            try:
                return self.energy2wavelength(self.energyMotor.getPosition())
            except:
                logging.getLogger("HWR").exception("EnergyScan: couldn't read energy")
                return None
        else:
            return self.defaultWavelength
    def getWavelengthLimits(self):
        lims=None
        if self.energyMotor is not None:
            if self.energyMotor.isReady():
                energy_lims=self.energyMotor.getLimits()
                lims=(self.energy2wavelength(energy_lims[1]),self.energy2wavelength(energy_lims[0]))
                if lims[0] is None or lims[1] is None:
                    lims=None
        return lims
    
    def startMoveEnergy(self,value,wait=True):
        logging.getLogger("HWR").info("Moving energy to (%s)" % value)
        try:
            value=float(value)
        except (TypeError,ValueError),diag:
            logging.getLogger("HWR").error("EnergyScan: invalid energy (%s)" % value)
            return False

        try:
            curr_energy=self.energyMotor.getPosition()
        except:
            logging.getLogger("HWR").exception("EnergyScan: couldn't get current energy")
            curr_energy=None

        if value!=curr_energy:
            logging.getLogger("HWR").info("Moving energy: checking limits")
            try:
                lims=self.energyMotor.getLimits()
            except:
                logging.getLogger("HWR").exception("EnergyScan: couldn't get energy limits")
                in_limits=False
            else:
                in_limits=value>=lims[0] and value<=lims[1]
                
            if in_limits:
                logging.getLogger("HWR").info("Moving energy: limits ok")
                self.previousResolution=None
                if self.resolutionMotor is not None:
                    try:
                        self.previousResolution=self.resolutionMotor.getPosition()
                    except:
                        logging.getLogger("HWR").exception("EnergyScan: couldn't get current resolution")
                self.moveEnergyCmdStarted()
                def change_egy():
                    try:
                        self.moveEnergy(value, wait=True)
                    except:
                        self.moveEnergyCmdFailed()
                    else:
                        self.moveEnergyCmdFinished(True)
                if wait:
                    change_egy()
                else:
                    gevent.spawn(change_egy)
            else:
                logging.getLogger("HWR").error("EnergyScan: energy (%f) out of limits (%s)" % (value,lims))
                return False          
        else:
            return None

        return True
    def startMoveWavelength(self,value, wait=True):
        energy_val=self.energy2wavelength(value)
        if energy_val is None:
            logging.getLogger("HWR").error("EnergyScan: unable to convert wavelength to energy")
            return False
        return self.startMoveEnergy(energy_val, wait)
    def cancelMoveEnergy(self):
        self.moveEnergy.abort()
    def energy2wavelength(self,val):
        if self.energy2WavelengthConstant is None:
            return None
        try:
            other_val=self.energy2WavelengthConstant/val
        except ZeroDivisionError:
            other_val=None
        return other_val
    def energyPositionChanged(self,pos):
        wav=self.energy2wavelength(pos)
        if wav is not None:
            self.emit('energyChanged', (pos,wav))
            self.emit('valueChanged', (pos, ))
    def energyLimitsChanged(self,limits):
        self.emit('energyLimitsChanged', (limits,))
        wav_limits=(self.energy2wavelength(limits[1]),self.energy2wavelength(limits[0]))
        if wav_limits[0]!=None and wav_limits[1]!=None:
            self.emit('wavelengthLimitsChanged', (wav_limits,))
        else:
            self.emit('wavelengthLimitsChanged', (None,))
    def moveEnergyCmdReady(self):
        if not self.moving:
            self.emit('moveEnergyReady', (True,))
    def moveEnergyCmdNotReady(self):
        if not self.moving:
            self.emit('moveEnergyReady', (False,))
    def moveEnergyCmdStarted(self):
        self.moving = True
        self.emit('moveEnergyStarted', ())
    def moveEnergyCmdFailed(self):
        self.moving = False
        self.emit('moveEnergyFailed', ())
    def moveEnergyCmdAborted(self):
        pass
        #self.moving = False
        #self.emit('moveEnergyFailed', ())
    def moveEnergyCmdFinished(self,result):
        self.moving = False
        self.emit('moveEnergyFinished', ())

    def getPreviousResolution(self):
        return (self.previousResolution,self.lastResolution)

    def restoreResolution(self):
        if self.resolutionMotor is not None:
            if self.previousResolution is not None:
                try:
                    self.resolutionMotor.move(self.previousResolution)
                except:
                    return (False,"Error trying to move the detector")
                else:
                    return (True,None)
            else:
                return (False,"Unknown previous resolution")
        else:
            return (False,"Resolution motor not defined")

    # Elements commands
    def getElements(self):
        logging.getLogger("HWR").debug('EnergyScan:getElements')
        elements=[]
        try:
            for el in self["elements"]:
                elements.append({"symbol":el.symbol, "energy":el.energy})
        except IndexError:
            pass
        return elements

    # Mad energies commands
    def getDefaultMadEnergies(self):
        logging.getLogger("HWR").debug('EnergyScan:getDefaultMadEnergies')
        energies=[]
        try:
            for el in self["mad"]:
                energies.append([float(el.energy), el.directory])
        except IndexError:
            pass
        return energies
        
    def getFilename(self, directory, filename, element, edge):
        filenameIn = os.path.join(directory, filename)
        filenameIn += "_" + element + "_" + "_".join(edge) + ".dat"
        return filenameIn
    
    def doEnergyScan(self, element, edge, directory, filename):
        logging.getLogger("HWR").info('EnergyScan: Element:%s Edge:%s' %(element,edge))    	

def StoreEnergyScanThread(db_conn, scan_info):
    scanInfo = dict(scan_info)
    dbConnection = db_conn
    
    blsampleid = scanInfo['blSampleId']
    scanInfo.pop('blSampleId')
    db_status=dbConnection.storeEnergyScan(scanInfo)
    if blsampleid is not None:
        try:
            energyscanid=int(db_status['energyScanId'])
        except:
            pass
        else:
            asoc={'blSampleId':blsampleid, 'energyScanId':energyscanid}
            dbConnection.associateBLSampleAndEnergyScan(asoc)
