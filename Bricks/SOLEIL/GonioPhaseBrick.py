
from BlissFramework import BaseComponents
from BlissFramework import Icons
from qt import *
import logging

###
### Brick to control a hardware object with two states
###
__category__ = 'SOLEIL'


class GonioPhaseBrick(BaseComponents.BlissWidget):

    def __init__(self, *args):
        BaseComponents.BlissWidget.__init__(self,*args)

        self.gonio_ho = None

        self.gonio_state = "OFF"
        self.gonio_phase = None
        self.auth = False

        self.addProperty('mnemonic','string','')
        self.addProperty('icons','string','')

        self.defineSignal('gonioAuthorizationChanged',())

        self.containerBox=QVGroupBox("none",self)
        self.containerBox.setInsideMargin(4)
        self.containerBox.setInsideSpacing(0)
        self.containerBox.setTitle("Goniometer")

        self.stateLabel = QLabel('<b> </b>', self.containerBox)

        self.buttonsBox=QHBox(self.containerBox)

        self.loadingButton=QPushButton("Loading",self.buttonsBox)
        self.loadingButton.setToggleButton(True)
        self.connect(self.loadingButton,SIGNAL('toggled(bool)'),self.setLoadingPhase)

        self.centringButton=QPushButton("Centring",self.buttonsBox)
        self.centringButton.setToggleButton(True)
        self.connect(self.centringButton,SIGNAL('toggled(bool)'),self.setCentringPhase)

        QVBoxLayout(self)

        self.layout().addWidget(self.containerBox)

        self.stateLabel.setAlignment(QLabel.AlignCenter)

        QToolTip.add(self.stateLabel,"Current control state")
        QToolTip.add(self.centringButton,"Sets gonio to CENTRING phase")
        QToolTip.add(self.loadingButton,"Sets gonio to LOADING phase")

    def setLoadingPhase(self, flag):
        if flag:
            self.loadingButton.blockSignals(True)
            self.gonio_ho.setLoadingPhase()
            self.centringButton.setState(QPushButton.Off)
            self.loadingButton.blockSignals(False)

    def setCentringPhase(self, flag):
        if flag:
            self.centringButton.blockSignals(True)
            self.loadingButton.setState(QPushButton.Off)
            self.gonio_ho.setCentringPhase()
            self.centringButton.blockSignals(False)

    def updateLabel(self,label):
        self.containerBox.setTitle(label)

    def updateState(self):

        if not self.gonio_state or self.gonio_state == "OFF":
            color = "#dddddd"  # off is grey
            stat_str = "OFF" 
        else:
            if self.auth:
                if str(self.gonio_state) == "2": 
                     color = "#ddffdd" # auth and standby is green
                     stat_str = "READY" 
                else:
                     color = "#fcfcdd" # auth and other is yellow
                     stat_str = "MOVING" 
            else:
                color = "#ffdddd" # not auth is red
                stat_str = "LOCKED" 

        self.stateLabel.setPaletteBackgroundColor(QColor(color))

        if self.auth:
            self.enableButtons(True)
        else:
            self.enableButtons(False)

        if self.gonio_phase:
            phase_str = "(%s)" % self.gonio_phase
        else:
            phase_str = ""

        self.stateLabel.setText('<b>%s</b>%s' % (stat_str,phase_str))

    def propertyChanged(self,propertyName,oldValue,newValue):

        if propertyName=='mnemonic':
            if self.gonio_ho is not None:
                self.disconnect(self.gonio_ho, PYSIGNAL('stateChanged'), self.gonioStateChanged)

            self.gonio_ho = self.getHardwareObject(newValue)

            self.connect(self.gonio_ho, PYSIGNAL('minidiffStateChanged'), self.gonioStateChanged)
            self.connect(self.gonio_ho, PYSIGNAL('operationPermitted'), self.authorizationChanged)
            self.connect(self.gonio_ho, PYSIGNAL('phaseChanged'), self.phaseChanged)
            logging.info("GONIO. Brick and hardware object are connected now")

            self.gonioStateChanged(self.gonio_ho.getState() )
            self.authorizationChanged( self.gonio_ho.getAuthorizationState() )

        elif propertyName=='icons':
            w=self.fontMetrics().width("Centring")
            icons_list=newValue.split()
            try:
                self.loadingButton.setPixmap(Icons.load(icons_list[0]))
            except IndexError:
                self.loadingButton.setText("Loading")
                self.loadingButton.setMinimumWidth(w)

            try:
                self.centringButton.setPixmap(Icons.load(icons_list[1]))
            except IndexError:
                self.centringButton.setText("Centring")
                self.centringButton.setMinimumWidth(w)

        else:
            BaseComponents.BlissWidget.propertyChanged(self,propertyName,oldValue,newValue)


    def enableButtons(self, enable):
        self.centringButton.setEnabled(enable)
        self.loadingButton.setEnabled(enable)

    def phaseChanged(self,phase):
        self.gonio_phase = phase
        self.updateState()

    def gonioStateChanged(self,state):
        self.gonio_state = state
        self.updateState()

    def authorizationChanged(self,auth):

        logging.debug("Authorization changed. it is %s " % str(auth))
        self.auth = auth

        self.emit(PYSIGNAL("gonioAuthorizationChanged"), (self.auth, ))
        self.updateState()
