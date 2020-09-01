import napari
import numpy as np

from pathlib import Path
from glob import glob
from napari.qt.threading import thread_worker
from qtpy import QtCore

from qtpy.QtWidgets import (
    QLabel,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QWidget,
)

from bg_atlasapi import BrainGlobeAtlas

from brainreg_segment.paths import Paths

from brainreg_segment.regions.IO import (
    save_label_layers,
    export_label_layers,
)

from brainreg_segment.tracks.IO import save_track_layers, export_splines

from brainreg_segment.atlas.utils import (
    get_available_atlases,
    display_brain_region_name,
)

##### LAYOUT HELPERS ################################################################################

from brainreg_segment.layout.utils import (
    disable_napari_btns,
    disable_napari_key_bindings,
)
from brainreg_segment.layout.gui_constants import (
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    COLUMN_WIDTH,
    BOUNDARIES_STRING,
    TRACK_FILE_EXT
)

from brainreg_segment.layout.gui_elements import (
    add_button,
    add_checkbox,
    add_float_box,
    add_int_box,
    add_combobox,
)

##### SEGMENTATION  ################################################################################
from brainreg_segment.segmentation_panels.regions import RegionSeg
from brainreg_segment.segmentation_panels.tracks import TrackSeg



class SegmentationWidget(QWidget):
    def __init__(
        self,
        viewer,
        boundaries_string=BOUNDARIES_STRING,
        ):
        super(SegmentationWidget, self).__init__()

        # general variables
        self.viewer = viewer

        # Disable / overwrite napari viewer functions 
        # that either do not make sense or should be avoided by the user
        disable_napari_btns(self.viewer)
        disable_napari_key_bindings()

        # track variables
        self.track_layers = []

        # region variables
        self.label_layers = []

        # atlas variables
        self.current_atlas_string = ''

        self.boundaries_string = boundaries_string
        
        # Set up segmentation methods 
        self.region_seg = RegionSeg(self)
        self.track_seg  = TrackSeg(self)
        
        # Generate main layout
        self.setup_main_layout()


    def setup_main_layout(self):
        ''' 
        Construct main layout of widget 
        
        ''' 
        self.layout = QGridLayout()
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.layout.setSpacing(4)

        # 3 Steps: 
        # - Loading panel 
        # - Segmentation methods (which are invisible at first)
        # - Saving panel

        self.add_loading_panel(1)
        self.track_seg.add_track_panel(2)
        self.region_seg.add_region_panel(3)
        self.add_saving_panel(4)
        
        # Take care of status label
        self.status_label = QLabel()
        self.status_label.setText("Ready")
        self.layout.addWidget(self.status_label, 5, 0)

        self.setLayout(self.layout)



    #################################################### PANELS ###############################################################


    def add_loading_panel(self, row):
        '''
        Loading panel consisting of 
        - Left column: 
            - Load project (sample space)
            - Load project (atlas space)
            - Atlas chooser 
        - Right column:
            Toggle visibility of segmentation
            methods


        '''
        self.load_data_panel = QGroupBox()
        self.load_data_layout = QGridLayout()

        self.load_button = add_button(
            "Load project (sample space)",
            self.load_data_layout,
            self.load_brainreg_directory_sample,
            0,
            0,
            minimum_width=COLUMN_WIDTH,
            alignment='left'
        )

        self.load_button_standard = add_button(
            "Load project (atlas space)",
            self.load_data_layout,
            self.load_brainreg_directory_standard,
            1,
            0,
            minimum_width=COLUMN_WIDTH,
            alignment='left'
        )

        self.add_atlas_menu(self.load_data_layout)

        self.show_trackseg_button = add_button(
            "Trace tracks",
            self.load_data_layout, 
            self.track_seg.toggle_track_panel, 
            0, 
            1,
            minimum_width=COLUMN_WIDTH
        )
        self.show_trackseg_button.setEnabled(False)

        self.show_regionseg_button = add_button(
            "Segment regions",
            self.load_data_layout, 
            self.region_seg.toggle_region_panel, 
            1, 
            1,
            minimum_width=COLUMN_WIDTH
        )
        self.show_regionseg_button.setEnabled(False)

        self.load_data_layout.setColumnMinimumWidth(1, COLUMN_WIDTH)
        self.load_data_panel.setLayout(self.load_data_layout)
        self.layout.addWidget(self.load_data_panel, row, 0, 1, 2)
        self.load_data_panel.setVisible(True)


    def add_saving_panel(self, row):
        '''
        Saving/Export panel 

        '''
        self.save_data_panel = QGroupBox()
        self.save_data_layout = QGridLayout()

        self.export_button = add_button(
            "To brainrender",
            self.save_data_layout,
            self.export_to_brainrender,
            0,
            0,
            visibility=False,
        )
        self.save_button = add_button(
            "Save", self.save_data_layout, self.save, 0, 1, visibility=False
        )

        self.save_data_layout.setColumnMinimumWidth(1, COLUMN_WIDTH)
        self.save_data_panel.setLayout(self.save_data_layout)
        self.layout.addWidget(self.save_data_panel, row, 0, 1, 2)

        self.save_data_panel.setVisible(False)



    #################################################### ATLAS INTERACTION ####################################################

    def add_atlas_menu(self, layout):
        list_of_atlasses = ['Load atlas']
        available_atlases = get_available_atlases()
        for atlas in available_atlases.keys():
            atlas_desc = f"{atlas} v{available_atlases[atlas]}"
            list_of_atlasses.append(atlas_desc)
            atlas_menu, _ = add_combobox(
            layout,
            None,
            list_of_atlasses,
            2,
            0,
            label_stack=True,
            callback=self.initialise_atlas,
            width=COLUMN_WIDTH
        )

        self.atlas_menu = atlas_menu

    def initialise_atlas(self, i):
        atlas_string = self.atlas_menu.currentText()

        if atlas_string != self.current_atlas_string: 
            self.remove_layers() 
        self.current_atlas_string = atlas_string

        atlas_name = atlas_string.split(" ")[0].strip()
        atlas = BrainGlobeAtlas(atlas_name)
        
        self.atlas = atlas
        self.base_layer = self.viewer.add_image(
            self.atlas.reference, name="Reference"
        )
        self.atlas_layer = self.viewer.add_labels(
            self.atlas.annotation,
            name=self.atlas.atlas_name,
            blending="additive",
            opacity=0.3,
            visible=False,
        )
        self.standard_space = True

        self.initialise_segmentation_interface()

        # Get / set directory
        self.set_output_directory()
        self.directory = self.directory / atlas_name
        self.paths = Paths(self.directory, atlas_space=True)


        #self.atlas_menu.setEnabled(False)
        self.status_label.setText("Ready")

        # Check / load previous regions and tracks
        self.region_seg.check_saved_region()
        self.track_seg.check_saved_track()



    #################################################### BRAINREG INTERACTION #################################################


    def load_brainreg_directory_sample(self):
        self.load_brainreg_directory(standard_space=False)

    def load_brainreg_directory_standard(self):
        self.load_brainreg_directory(standard_space=True)

    def load_brainreg_directory(self, standard_space=True):
        if standard_space:
            plugin = "brainreg_standard"
            self.standard_space = True
        else:
            plugin = "brainreg"
            self.standard_space = False

        self.status_label.setText("Loading...")
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        self.directory = QFileDialog.getExistingDirectory(
            self, "Select brainreg directory", options=options,
        )
        if self.directory != "":
            try:
                self.directory = Path(self.directory)
                self.remove_layers()

                self.viewer.open(str(self.directory), plugin=plugin)
                self.paths = Paths(
                    self.directory, standard_space=standard_space,
                )

                self.initialise_loaded_data()

                # Check / load previous regions and tracks
                self.region_seg.check_saved_region()
                self.track_seg.check_saved_track()
                
            except ValueError:
                print(
                    f"The directory ({self.directory}) does not appear to be "
                    f"a brainreg directory, please try again."
                )

    def initialise_loaded_data(self):
        # for consistency, don't load this
        try:
            self.viewer.layers.remove(self.boundaries_string)
        except KeyError:
            pass

        self.base_layer = self.viewer.layers["Registered image"]
        self.metadata = self.base_layer.metadata
        self.atlas = self.metadata["atlas_class"]
        self.atlas_layer = self.viewer.layers[self.metadata["atlas"]]
        self.initialise_segmentation_interface()



    #################################################### MORE LAYOUT COMPONENTS ###########################################
    
    
    def initialise_segmentation_interface(self):
        self.reset_variables()
        self.initialise_image_view()

        @self.atlas_layer.mouse_move_callbacks.append
        def display_region_name(layer, event):
            display_brain_region_name(layer, self.atlas.structures)

        self.save_data_panel.setVisible(True)
        self.save_button.setVisible(True)
        self.export_button.setVisible(self.standard_space)
        self.show_regionseg_button.setEnabled(True)
        self.show_trackseg_button.setEnabled(True)
        self.status_label.setText("Ready")

        
    def initialise_image_view(self):
        self.set_z_position()

    def set_z_position(self):
        midpoint = int(round(len(self.base_layer.data) / 2))
        self.viewer.dims.set_point(0, midpoint)

    def set_output_directory(self):
        self.status_label.setText("Loading...")
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        self.directory = QFileDialog.getExistingDirectory(
            self, "Select output directory", options=options,
        )
        if self.directory != "":
            self.directory = Path(self.directory)

    def reset_variables(self):
        # TODO: Re-implement this method

        #self.mean_voxel_size = int(
        #    np.sum(self.atlas.resolution) / len(self.atlas.resolution)
        #)
        #self.point_size = self.point_size / self.mean_voxel_size
        #self.spline_size = self.spline_size / self.mean_voxel_size
        #self.brush_size = self.brush_size / self.mean_voxel_size
        return

    def remove_layers(self):
        '''
        TODO: This needs work. Runs into an error currently 
        when switching from a freshly annotated project to another one 

        '''
        if len(self.viewer.layers) != 0:
            # Remove old layers
            for layer in list(self.viewer.layers):
                self.viewer.layers.remove(layer)

        self.track_layers = []
        self.label_layers = []


    def save(self):
        if self.label_layers or self.track_layers:
            print("Saving")
            worker = save_all(
                self.paths.regions_directory,
                self.paths.tracks_directory,
                self.label_layers,
                self.track_layers,
                track_file_extension=TRACK_FILE_EXT,
            )
            worker.start()

    def export_to_brainrender(self):
        print("Exporting")
        max_axis_2 = self.base_layer.shape[2]
        worker = export_all(
            self.paths.regions_directory,
            self.paths.tracks_directory,
            self.label_layers,
            self.splines,
            self.spline_names,
            self.atlas.resolution[0],
            max_axis_2,
        )
        worker.start()


@thread_worker
def export_all(
    regions_directory,
    tracks_directory,
    label_layers,
    splines,
    spline_names,
    resolution,
    max_axis_2,
):
    if label_layers:
        # TODO: this function does not exist
        export_label_layers(regions_directory, label_layers)

    if splines:
        export_splines(
            tracks_directory, splines, spline_names, resolution, max_axis_2
        )
    print("Finished!\n")


@thread_worker
def save_all(
    regions_directory,
    tracks_directory,
    label_layers,
    points_layers,
    track_file_extension=".points",
):
    if label_layers:
        save_label_layers(regions_directory, label_layers)

    if points_layers:
        save_track_layers(
            tracks_directory,
            points_layers,
            track_file_extension=track_file_extension,
        )
    print("Finished!\n")









def main():
    print("Loading segmentation GUI.\n ")
    with napari.gui_qt():
        viewer = napari.Viewer(title="Segmentation GUI")
        viewer.window.resize(WINDOW_WIDTH,WINDOW_HEIGHT)
        widget = SegmentationWidget(viewer)
        viewer.window.add_dock_widget(widget, name="General", area="right")


if __name__ == "__main__":
    main()