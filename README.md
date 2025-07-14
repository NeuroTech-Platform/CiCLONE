# CiCLONE : Cico Cardinale's Localization Of Neuro-electrodes

![CiCLONE Logo](docs/images/ciclone_banner.png)

## Develop

Use `poetry` (installed via `pipx`) to setup the virtual env and run it nicely for you.
```console
# Pick a valid Python3 version, e.g. 3.11 or 3.12

$ poetry env use $(pyenv which python3.11)
or
$ poetry env use $(pyenv which python3.12)
then
$ poetry install
```

## Run it

First, ensure that the **config.yaml** file is present in the config folder in the same directory as **main.py** and that the output directory exists on your machine. If not copy **config.yaml.template** to **config.yaml** and update the fields inside the file.

The pipeline consists of multiple stages that can be run independently or all at once. Each stage contains one or more operations. The available operations are:

- `crop` - Crop an image file [Input_File, Output_File]
- `move` - Move a file to a directory [Input_File, Output_Dir] 
- `coregister` - Coregister an image to a reference [Input_File, Reference_File, Output_File]
- `subtract` - Subtract one image from another [Input_File, Subtract_File, Output_File]
- `threshold` - Apply thresholding to an image [Input_File, Output_File]
- `apply_transformation` - Apply a transformation matrix [Input_File, Transformation_File, Reference_File, Output_File]
- `extract_brain` - Extract brain from an image [Input_File, Output_File]
- `mask` - Apply a binary mask to an image [Input_File, Mask_File, Output_File]
- `register_ct_to_mni` - Register CT to MNI space [Input_File, Output_File]
- `register_mri_to_mni` - Register MRI to MNI space [Input_File, Output_File]
- `reconstruct` - Run FreeSurfer reconstruction [Input_File, Output_Dir]
- `open_fsleyes` - Open FSLeyes viewer [Input_File]

The pipeline configuration is defined in YAML format. Each stage has a name and a list of operations. For example:

```yaml
stages:
  - name: preprocessing
    operations:
      - type: crop
        workdir: preop/ct
        files: ["${name}_CT_Bone", "${name}_CT_Bone_C"]
      - type: move
        workdir: preop/ct
        files: ["${name}_CT_Bone_C", "${subj_dir}/processed_tmp"]
```

## Usage

All commands require the `--directory` flag to specify where subject data will be stored. For example:

```console
$ ciclone --directory /path/to/output/directory [command] [options]
```

## Step 1 : Create a folder for each subject

```console
$ ciclone --directory /path/to/output/directory --create-folder subject1 subject<N>
```

## Step 2 : Run all stages or a specific one

```console
$ ciclone --directory /path/to/output/directory --subjects subject1 subject<N>
```
or 
```console
$ ciclone --directory /path/to/output/directory --subjects subject1 subject<N> --stages <NAME_OF_THE_STAGE>
```

## Step 3 : Mark your electrodes in 3D Slicer

Here you are on your own. You need to mark your electrodes in 3D Slicer using the **r_SUBJECTID_seeg_masked** file and your subject CT and/ or MRI and save the coordinates in a JSON file.

## Step 4 : Transform coordinates from Subject space to MNI space

```console
$ ciclone --directory /path/to/output/directory --subjects subject1 subject<N> --transform-coordinates /path/to/3D-SlicerJSON/file
```

The transformed coordinates will be saved in the same directory as the input JSON file with the prefix "MNI_".
