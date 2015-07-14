#
#  Project: MXCuBE
#  https://github.com/mxcube.
#
#  This file is part of MXCuBE software.
#
#  MXCuBE is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  MXCuBE is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with MXCuBE.  If not, see <http://www.gnu.org/licenses/>.

import copy

from PyQt4 import QtCore
from PyQt4 import QtGui

import Qt4_queue_item
import Qt4_GraphicsManager
import queue_model_objects_v1 as queue_model_objects
import queue_model_enumerables_v1 as queue_model_enumerables

from BlissFramework.Utils import Qt4_widget_colors
from Qt4_data_path_widget import DataPathWidget
from Qt4_processing_widget import ProcessingWidget
from Qt4_acquisition_widget import AcquisitionWidget
from Qt4_create_task_base import CreateTaskBase


class CreateDiscreteWidget(CreateTaskBase):
    """
    Descript. :
    """
    def __init__(self, parent=None, name=None, fl=0):
        """
        Descript. :
        """

        CreateTaskBase.__init__(self, parent, name, QtCore.Qt.WindowFlags(fl), "Standart")

        if not name:
            self.setObjectName("Qt4_create_discrete_widget")

        # Hardware objects ----------------------------------------------------

        # Internal variables --------------------------------------------------
        self.previous_energy = None
        self.init_models()

        # Graphic elements ----------------------------------------------------
        self._acq_widget =  AcquisitionWidget(self, "acquisition_widget",
             layout='vertical', acq_params=self._acquisition_parameters,
             path_template=self._path_template)

        self._data_path_gbox = QtGui.QGroupBox('Data location', self)
        self._data_path_gbox.setObjectName('data_path_gbox')        
        self._data_path_widget = \
            DataPathWidget(self._data_path_gbox,
                           'create_dc_path_widget',
                           data_model=self._path_template,
                           layout='vertical')

        self._processing_gbox = QtGui.QGroupBox('Processing', self)
        self._processing_gbox.setObjectName('processing_gbox')
        self._processing_widget = \
            ProcessingWidget(self._processing_gbox,
                             data_model=self._processing_parameters)
       
        # Layout --------------------------------------------------------------
        self._data_path_gbox_layout = QtGui.QVBoxLayout(self)
        self._data_path_gbox_layout.addWidget(self._data_path_widget)
        self._data_path_gbox_layout.setSpacing(0)
        self._data_path_gbox_layout.setContentsMargins(0, 0, 0, 0)
        self._data_path_gbox.setLayout(self._data_path_gbox_layout)

        self._processing_gbox_layout = QtGui.QVBoxLayout(self)
        self._processing_gbox_layout.addWidget(self._processing_widget)
        self._processing_gbox_layout.setSpacing(0)
        self._processing_gbox_layout.setContentsMargins(0, 0, 0, 0)
        self._processing_gbox.setLayout(self._processing_gbox_layout)

        self.main_layout = QtGui.QVBoxLayout(self)
        self.main_layout.addWidget(self._acq_widget)
        self.main_layout.addWidget(self._data_path_gbox)
        self.main_layout.addWidget(self._processing_gbox)
        self.main_layout.addSpacing(10)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        # SizePolicies --------------------------------------------------------
        """self._acq_widget.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                       QtGui.QSizePolicy.Fixed)
        self._data_path_gbox.setSizePolicy(QtGui.QSizePolicy.Expanding,
                           QtGui.QSizePolicy.Expanding)
        self._processing_gbox.setSizePolicy(QtGui.QSizePolicy.Expanding,
                           QtGui.QSizePolicy.Expanding)"""
        
        # Qt signal/slot connections ------------------------------------------
        self._processing_gbox.toggled.connect(self._use_processing_toggled)
        self._data_path_widget.data_path_layout.prefix_ledit.textChanged.\
             connect(self._prefix_ledit_change)
        self._data_path_widget.data_path_layout.run_number_ledit.textChanged.\
             connect(self._run_number_ledit_change)

        self.connect(self._acq_widget, QtCore.SIGNAL('mad_energy_selected'),
                     self.mad_energy_selected)

        self.connect(self._acq_widget,
                     QtCore.SIGNAL("pathTemplateChanged"),
                     self.handle_path_conflict)

        self.connect(self._data_path_widget,
                     QtCore.SIGNAL("pathTemplateChanged"),
                     self.handle_path_conflict)

        # Other ---------------------------------------------------------------

    def init_models(self):
        """
        Descript. :
        """
        CreateTaskBase.init_models(self)
        self._energy_scan_result = queue_model_objects.EnergyScanResult()
        self._processing_parameters = queue_model_objects.ProcessingParameters()

    def set_tunable_energy(self, state):
        """
        Descript. :
        """
        self._acq_widget.set_tunable_energy(state)

    def update_processing_parameters(self, crystal):
        """
        Descript. :
        """
        self._processing_parameters.space_group = crystal.space_group
        self._processing_parameters.cell_a = crystal.cell_a
        self._processing_parameters.cell_alpha = crystal.cell_alpha
        self._processing_parameters.cell_b = crystal.cell_b
        self._processing_parameters.cell_beta = crystal.cell_beta
        self._processing_parameters.cell_c = crystal.cell_c
        self._processing_parameters.cell_gamma = crystal.cell_gamma
        self._processing_widget.update_data_model(self._processing_parameters)

    def mad_energy_selected(self, name, energy, state):
        """
        Descript. :
        """
        item = self._current_selected_items[0]
        model = item.get_model()
        
        if state:
            self._path_template.mad_prefix = name
        else:
            self._path_template.mad_prefix = ''

        run_number = self._beamline_setup_hwobj.queue_model_hwobj.\
            get_next_run_number(self._path_template)

        data_path_widget = self.get_data_path_widget()
        data_path_widget.set_run_number(run_number)
        data_path_widget.set_prefix(self._path_template.base_prefix)

        if self.isEnabled():
            if isinstance(item, Qt4_queue_item.TaskQueueItem) and \
                   not isinstance(item, Qt4_queue_item.DataCollectionGroupQueueItem):
                model.set_name(self._path_template.get_prefix())
                item.setText(0, model.get_name())

    def single_item_selection(self, tree_item):
        """
        Descript. :
        """
        CreateTaskBase.single_item_selection(self, tree_item)
        if isinstance(tree_item, Qt4_queue_item.SampleQueueItem):
            sample_model = tree_item.get_model()
            #self._processing_parameters = copy.deepcopy(self._processing_parameters)
            self._processing_parameters = sample_model.processing_parameters
            self._processing_widget.update_data_model(self._processing_parameters)
            self._acq_widget.disable_inverse_beam(False)

        elif isinstance(tree_item, Qt4_queue_item.DataCollectionQueueItem):
            dc = tree_item.get_model()

            if dc.experiment_type != queue_model_enumerables.EXPERIMENT_TYPE.HELICAL:
                if dc.is_executed():
                    self.setDisabled(True)
                else:
                    self.setDisabled(False)

                sample_data_model = self.get_sample_item(tree_item).get_model()
                energy_scan_result = sample_data_model.crystals[0].energy_scan_result
                self._acq_widget.set_energies(energy_scan_result)

                self._acq_widget.disable_inverse_beam(True)
                
                self._path_template = dc.get_path_template()
                self._data_path_widget.update_data_model(self._path_template)

                self._acquisition_parameters = dc.acquisitions[0].acquisition_parameters
                self._acq_widget.update_data_model(self._acquisition_parameters,
                                                    self._path_template)
                self.get_acquisition_widget().use_osc_start(True)
                if len(dc.acquisitions) == 1:
                    self.select_shape_with_cpos(self._acquisition_parameters.\
                                                centred_position)

                self._processing_parameters = dc.processing_parameters
                self._processing_widget.update_data_model(self._processing_parameters)
            else:
                self.setDisabled(True)
        else:
            self.setDisabled(True)

    def approve_creation(self):
        """
        Descript. :
        """
        result = CreateTaskBase.approve_creation(self)
        selected_shapes = self._graphics_manager_hwobj.get_selected_shapes()

        for shape in selected_shapes:
            if isinstance(shape, Qt4_GraphicsManager.GraphicsItemPoint):
                result = True
        return result

    # Called by the owning widget (task_toolbox_widget) to create
    # a collection. When a data collection group is selected.
    def _create_task(self, sample, shape):
        """
        Descript. :
        """
        tasks = []

        if not shape:
            cpos = queue_model_objects.CentredPosition()
            cpos.snapshot_image = self._graphics_manager_hwobj.get_snapshot()
        else:
            # Shapes selected and sample is mounted, get the
            # centred positions for the shapes
            if isinstance(shape, Qt4_GraphicsManager.GraphicsItemPoint):
                snapshot = self._graphics_manager_hwobj.\
                           get_snapshot([shape])

                cpos = copy.deepcopy(shape.get_centred_positions()[0])
                cpos.snapshot_image = snapshot

        if self._acq_widget.use_inverse_beam():
            total_num_images = self._acquisition_parameters.num_images
            subwedge_size = self._acq_widget.get_num_subwedges()
            osc_range = self._acquisition_parameters.osc_range
            osc_start = self._acquisition_parameters.osc_start
            run_number = self._path_template.run_number

            subwedges = queue_model_objects.create_inverse_beam_sw(total_num_images,
                        subwedge_size, osc_range, osc_start, run_number)

            self._acq_widget.set_use_inverse_beam(False)

            for sw in subwedges:
                tasks.extend(self.create_dc(sample, sw[3], sw[0], sw[1],
                                            sw[2], cpos=cpos,
                                            inverse_beam = True))
                self._path_template.run_number += 1
        else:
            tasks.extend(self.create_dc(sample, cpos=cpos))
            self._path_template.run_number += 1

        return tasks
    
    def create_dc(self, sample, run_number = None, start_image = None,
                  num_images = None, osc_start = None, sc = None,
                  cpos=None, inverse_beam = False):
        """
        Descript. :
        """
        tasks = []

        # Acquisition for start position
        acq = self._create_acq(sample)
       
        if run_number:        
            acq.path_template.run_number = run_number

        if start_image:
            acq.acquisition_parameters.first_image = start_image
            acq.path_template.start_num = start_image

        if num_images:
            acq.acquisition_parameters.num_images = num_images
            acq.path_template.num_files = num_images

        if osc_start:
            acq.acquisition_parameters.osc_start = osc_start

        if inverse_beam:
            acq.acquisition_parameters.inverse_beam = False

        acq.acquisition_parameters.centred_position = cpos

        processing_parameters = copy.deepcopy(self._processing_parameters)
        dc = queue_model_objects.DataCollection([acq], sample.crystals[0],
                                                processing_parameters)
        dc.set_name(acq.path_template.get_prefix())
        dc.set_number(acq.path_template.run_number)
        dc.experiment_type = queue_model_enumerables.EXPERIMENT_TYPE.NATIVE

        tasks.append(dc)

        return tasks
