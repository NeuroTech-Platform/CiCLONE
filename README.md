# CLONE : Cico's Localization Of Neuro-electrodes

## Develop

Use `poetry` (installed via `pipx`) to setup the virtual env and run it nicely for you.

```console
# Pick a valid Python3 version, e.g. 3.10 or 3.11

$ poetry env use $(pyenv which python3.10)
$ poetry env use $(pyenv which python3.11)

$ poetry install
```

## Run it

First, ensure that the **config.yaml** file is present in the config folder in the same directory as **main.py** and that the output directory exists on your machine. If not copy **config.yaml.template** to **config.yaml** and update the fields inside the file.

There are multiple operations available that can be combined however you see fit : 
- crop => Parameters [Input_File, Output_File]
- move => Parameters [Input_File, Output_Dir]
- coregister => Parameters [Input_File, Reference_File, Output_File]
- subtract => Parameters [Input_File, Subtract_File, Output_File]
- threshold => Parameters [Input_File, Output_File]
- apply_transformation => Parameters [Input_File, Transformation_File, Reference_File, Output_File]
- extract_brain => Parameters [Input_File, Output_File]
- mask => Parameters [Input_File, Mask_File, Output_File]

You can define one or multiple stages for you analysis following this nomenclature:

```yaml
stages:
  - name: stage1_name
    operations:
      - type: crop
        workdir: postop/ct
        files: ["${name}_CT_Bone", "${name}_CT_Bone_C"]
```

You can have multiple stages with multiple operations, combine based on the extract above and the operations list provided.

```workdir``` will be used before each operation to ensure that we are in the correct folder before running. Correct values for ```workdir``` are:
- preop/ct
- preop/mri
- postop/ct
- postop/mri
- processed_tmp

There are two environements variable that allows for more adaptability: 
- ```${name}``` : will be replaced by the subject name defined via command line when running the script
- ```${subj_dir}``` : will be replaced by the directory pointing to the data when running the script

## Commands

To create the folder and subfolders necessary (for one or multiple subjects)
```console
$ clone --subjects subject1 subjectN --create-folder
```

To run any stage of your configuration file (for one or multiple subjects)
```console
$ clone --subjects subject1 subjectN --stage <STAGE_NAME>
```

To run all stages (for one or multiple subjects)
```console
$ clone --subjects subject1 subjectN
```