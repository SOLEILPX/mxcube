# 
# From HutchMenuBrick.py
#
from qt import *
from BlissFramework import Icons
import logging
import MiniDiff
import HutchMenuBrick
import CommandMenuBrick
import os
import tempfile

from Qub.Objects.QubDrawingManager import QubPointDrawingMgr, Qub2PointSurfaceDrawingMgr, QubAddDrawing
from Qub.Objects.QubDrawingManager import QubContainerDrawingMgr
from Qub.Objects.QubDrawingCanvasTools import QubCanvasTarget
from Qub.Objects.QubDrawingCanvasTools import QubCanvasVLine
from Qub.Objects.QubDrawingCanvasTools import QubCanvasHLine
from Qub.Objects.QubDrawingCanvasTools import QubCanvasBeam
from Qub.Objects.QubDrawingCanvasTools import QubCanvasSlitbox
from Qub.Objects.QubDrawingCanvasTools import QubCanvasRectangle
from Qub.Objects.QubDrawingCanvasTools import QubCanvasScale
from Qub.Objects.QubDrawingEvent import QubMoveNPressed1Point
from Qub.Tools import QubImageSave
from BlissFramework.Utils import widget_colors


__category__ = 'SOLEIL'

###
### Sample centring brick
###
class SoleilHutchMenuBrick(HutchMenuBrick.HutchMenuBrick):

    def __init__(self, *args):
        HutchMenuBrick.HutchMenuBrick.__init__(self, *args)

        self.minidiff = None
        self.slitbox  = None
        self.sampleChanger=None
        self.collectObj = None
        self.queue_hwobj = None
        #self._bx, self._by = (10., 5)
        self._bx, self._by = (None, None)
        #self.allowMoveToBeamCentring = False

        # Define properties
        self.addProperty('minidiff','string','')
        self.addProperty('dataCollect','string','')
        self.addProperty('slitbox','string','')
        self.addProperty('samplechanger','string','')
        self.addProperty('extraCommands','string','')
        self.addProperty('extraCommandsIcons','string','')
        self.addProperty('icons','string','')
        self.addProperty('label','string','Sample centring')
        #self.addProperty('displaySlitbox', 'boolean', True)
        self.addProperty('displayBeam', 'boolean', True)
        self.addProperty('queue', 'string', '/queue')

        # Define signals and slots
        self.defineSignal('enableMinidiff',())
        self.defineSignal('centringStarted',())
        self.defineSignal('centringAccepted',())
        self.defineSignal('getView',())
        self.defineSignal('beamPositionChanged', ())
        self.defineSignal('calibrationChanged', ())
        self.defineSignal('newCentredPos', ())
        #self.defineSignal('setMoveToBeamState', ())
        self.defineSlot('setDirectory',())
        self.defineSlot('setPrefix',())
        #self.defineSlot('movedToBeam', ())
        self.defineSlot('startCentring', ())
        self.defineSlot('rejectCentring', ())
        self.defineSlot('setSample',())
        #self.defineSlot('enableAutoStartLoopCentring', ())
        self.defineSlot('getSnapshot',())
        
        self.sampleCentreBox=QVBox(self)
        #self.sampleCentreBox.setInsideMargin(11)
        #self.sampleCentreBox.setInsideSpacing(0)

        #self.modeBox=QVButtonGroup(self.sampleCentreBox)
        #self.modeBox.setFrameShape(self.modeBox.NoFrame)
        #self.modeBox.setInsideMargin(0)
        #self.modeBox.setInsideSpacing(0)            
        #QObject.connect(self.modeBox,SIGNAL('clicked(int)'),self.centringModeChanged)
        #self.userConfirmsButton=QCheckBox("User confirms", self.sampleCentreBox)
        #self.userConfirmsButton.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
        #self.userConfirmsButton.setChecked(True)

        self.buttonsBox=QVBox(self.sampleCentreBox)
        self.buttonsBox.setSpacing(0)

        self.buttonCentre=MenuButton(self.buttonsBox,"Centre")
        self.buttonCentre.setMinimumSize(QSize(75,50))
        self.connect(self.buttonCentre,PYSIGNAL('executeCommand'),self.centreSampleClicked)
        self.connect(self.buttonCentre,PYSIGNAL('cancelCommand'),self.cancelCentringClicked)

        self.buttonAccept = QToolButton(self.buttonsBox)
        self.buttonAccept.setUsesTextLabel(True)
        self.buttonAccept.setTextLabel("Save")
        self.buttonAccept.setMinimumSize(QSize(75,50))
        self.buttonAccept.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.buttonAccept.setEnabled(False)
        QObject.connect(self.buttonAccept,SIGNAL('clicked()'),self.acceptClicked)
        self.standardColor=None

        self.buttonReject = QToolButton(self.buttonsBox)
        self.buttonReject.setUsesTextLabel(True)
        self.buttonReject.setTextLabel("Reject")
        self.buttonReject.setMinimumSize(QSize(75,50))
        self.buttonReject.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.buttonReject.setEnabled(False)
        self.buttonReject.hide()
        QObject.connect(self.buttonReject,SIGNAL('clicked()'),self.rejectClicked)

        #HorizontalSpacer4(self.sampleCentreBox)

        self.extraCommands=CommandMenuBrick.CommandMenuBrick(self.sampleCentreBox)
        self.extraCommands['showBorder']=False

        self.buttonSnapshot = QToolButton(self.sampleCentreBox)
        self.buttonSnapshot.setUsesTextLabel(True)
        self.buttonSnapshot.setTextLabel("Snapshot")
        self.buttonSnapshot.setMinimumSize(QSize(75,50))
        self.buttonSnapshot.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        QObject.connect(self.buttonSnapshot,SIGNAL('clicked()'),self.saveSnapshot)

        self.buttonBeamPosition = QToolButton(self.sampleCentreBox)
        self.buttonBeamPosition.setUsesTextLabel(True)
        self.buttonBeamPosition.setTextLabel("CheckBeam")
        self.buttonBeamPosition.setMinimumSize(QSize(75,50))
        self.buttonBeamPosition.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        QObject.connect(self.buttonBeamPosition, SIGNAL('clicked()'), self.beamPositionCheck)
        #HorizontalSpacer3(self.sampleCentreBox)

        self.centringButtons=[]
        self.defaultBackgroundColor=None
        self.insideDataCollection=False        
        self.currentCentring = None
        self.isMoving=False
        self.isShooting=False
        self.directory="/tmp"
        self.prefix="snapshot"
        self.fileIndex=1
        self.formatType="png"

        self.clickedPoints=[]
        self.selectedSamples=None

        # Layout
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        QHBoxLayout(self)        
        self.layout().addWidget(self.sampleCentreBox)

        self.instanceSynchronize("")

        self.resetMethods={MiniDiff.MiniDiff.MANUAL3CLICK_MODE:self.manualCentreReset,
            MiniDiff.MiniDiff.C3D_MODE:self.automaticCentreReset}
            #MiniDiff.MiniDiff.MOVE_TO_BEAM_MODE:self.moveToBeamReset}
        self.successfulMethods={MiniDiff.MiniDiff.MANUAL3CLICK_MODE:None,
            MiniDiff.MiniDiff.C3D_MODE:self.automaticCentreSuccessful}
            #MiniDiff.MiniDiff.MOVE_TO_BEAM_MODE:self.moveToBeamSuccessful}

    def beamPositionCheck(self):
        self.minidiff.beamPositionCheck()
        
    def connectNotify(self, signalName):
        if signalName=='beamPositionChanged':
            if self.minidiff and self.minidiff.isReady():
                self.emit(PYSIGNAL("beamPositionChanged"), (self.minidiff.getBeamPosX, self.minidiff.getBeamPosY))
        elif signalName=='calibrationChanged':
            if self.minidiff and self.minidiff.isReady():
                try:
                    self.emit(PYSIGNAL("calibrationChanged"), (1e3/self.minidiff.pixelsPerMmY, 1e3/self.minidiff.pixelsPerMmZ))
                except:
                    pass

    # Event when the minidiff is in ready state
    def miniDiffReady(self):
        #import pdb;pdb.set_trace()
        try:
            pxmmy=self.minidiff.pixelsPerMmY
            pxmmz=self.minidiff.pixelsPerMmZ
            self.emit(PYSIGNAL("beamPositionChanged"), (self.minidiff.getBeamPosX, self.minidiff.getBeamPosY))
        except:
            pxmmy=None
            pxmmz=None 
        if pxmmy is not None and pxmmz is not None:
            self.sampleCentreBox.setEnabled(True)
            self.updateBeam()
        else:
            self.miniDiffNotReady()

    def run(self):
        if self.minidiff is not None:
            zoom=self.minidiff.zoomMotor
            if zoom is not None:
                if zoom.isReady():
                    self.zoomPositionChanged(zoom.getCurrentPositionName(),0)

        keys = {}
        self.emit(PYSIGNAL('getView'),(keys,))
        self.__drawing = keys.get('drawing',None)
        self.__view = keys.get('view',None)
        if self.minidiff is not None:
          self.minidiff._drawing = self.__drawing

        try:
            self.__point, _ = QubAddDrawing(self.__drawing, QubPointDrawingMgr, QubCanvasTarget)
            self.__point.setEndDrawCallBack(self.__endDrawingPoint)
            self.__point.setColor(Qt.yellow)
            
            self.__autoCentringPoint, _ = QubAddDrawing(self.__drawing, QubPointDrawingMgr, QubCanvasTarget)
            self.__autoCentringPoint.setColor(Qt.green)

            self.__helpLine, _ = QubAddDrawing(self.__drawing, QubPointDrawingMgr, QubCanvasVLine)
            self.__helpLine.setAutoDisconnectEvent(True)
            self.__helpLine.setExclusive(False)
            self.__helpLine.setColor(Qt.yellow)

            self.__rectangularBeam, _ = QubAddDrawing(self.__drawing, QubContainerDrawingMgr, QubCanvasSlitbox)
            #self.__rectangularBeam.show()
            #self.__rectangularBeam.setSlitboxSize(0,0)
            xsize, ysize = self.minidiff.getBeamSize()
            self.__rectangularBeam.setSlitboxSize( xsize *self.minidiff.pixelsPerMmY/1e3, ysize*self.minidiff.pixelsPerMmZ/1e3) 
            self.__rectangularBeam.set_xMid_yMid(self.minidiff.getBeamPosX(), self.minidiff.getBeamPosY())
            self.__rectangularBeam.setColor(Qt.red)
            self.__rectangularBeam.setSlitboxPen(QPen(Qt.blue))
            self.__rectangularBeam.show()
            
            self.__beam, _ = QubAddDrawing(self.__drawing, QubContainerDrawingMgr, QubCanvasBeam) 
            self.__beam.setPen(QPen(Qt.blue))
            self.__beam.show()

            self.__pointer, _, _ = QubAddDrawing(self.__drawing, QubPointDrawingMgr, QubCanvasHLine, QubCanvasVLine)
            self.__pointer.setDrawingEvent(QubMoveNPressed1Point)
            self.__pointer.setExclusive(False)
            self.__pointer.setColor(Qt.yellow)

            self.__scale, scale = QubAddDrawing(self.__drawing, QubContainerDrawingMgr, QubCanvasScale)
            self.sx = self.__scale.setXPixelSize
            self.sy = self.__scale.setYPixelSize
            self.__scale.show()

            try:
                self.__scale.setXPixelSize(self.__scaleX)
                self.__scale.setYPixelSize(self.__scaleY)
            except AttributeError:
                pass
            else:
                self.emit(PYSIGNAL("calibrationChanged"), (self.__scaleX, self.__scaleY))
                self.slitsPositionChanged()
                self.updateBeam(force=True)
        except:
            logging.getLogger().exception("HutchMenuBrick: problem starting up display")

    def updateBeam(self,force=False):
        logging.info("updateBeam")
        #if self["displayBeam"]:
        beam_x, beam_y = (self.minidiff.getBeamPosX, self.minidiff.getBeamPosY)
        self.__rectangularBeam.set_xMid_yMid(self.minidiff.getBeamPosX(), self.minidiff.getBeamPosY())
        try:
            self.__beam.move(beam_x, beam_y)
            try:
                #get_beam_info = self.minidiff.getCommandObject("getBeamInfo")
                if force or get_beam_info.isSpecReady():
                    self.minidiff.getBeamInfo(callback= self._updateBeam, error_callback=None)
                    
                #get_beam_info(callback=self._updateBeam, error_callback=None)
            except:
                logging.getLogger().exception("Could not get beam size: cannot display beam")
                self.__beam.hide()
        except AttributeError:
            pass


    # Zoom changed: update pixels per mm
    def zoomPositionChanged(self,position,offset):
        pxmmy, pxmmz, pxsize_y, pxsize_z = None,None,None,None

        if offset is None:
          # unknown zoom pos.
          try:
            self.__scale.hide()
            self.__rectangularBeam.hide()
            self.__beam.hide()
          except AttributeError:
            self.__scaleX = None
            self.__scaleY = None
        else:
            if self.minidiff is not None:
                pxmmy=self.minidiff.pixelsPerMmY
                pxmmz=self.minidiff.pixelsPerMmZ
                if pxmmy is not None and pxmmz is not None:
                    pxsize_y = 1e-3 / pxmmy
                    pxsize_z = 1e-3 / pxmmz

                try:
                    self.sx(pxsize_y)
                    self.sy(pxsize_z)
                except AttributeError:
                    self.__scaleX = pxsize_y
                    self.__scaleY = pxsize_z
                else:
                    self.emit(PYSIGNAL("calibrationChanged"), (pxsize_y, pxsize_z))
                    self.__beam.move(self.minidiff.getBeamPosX(), self.minidiff.getBeamPosY())
                    xsize, ysize = self.minidiff.getBeamSize()
                    self.__rectangularBeam.setSlitboxSize(xsize*pxmmy/1e3, ysize*pxmmz/1e3)
                    self.__rectangularBeam.set_xMid_yMid(self.minidiff.getBeamPosX(), self.minidiff.getBeamPosY())
                    self._drawBeam()
                    self.__scale.show()
               
