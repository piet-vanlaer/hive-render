#!/bin/bash

# BLEND_FILE injected from lambda
# BLEND_DIR injected from lambda
# START injected from lambda
# END injected from lambda
# FORMAT injected from lambda
# JOB_ID injected from lambda





echo "BEGIN" >> /tmp/output.log

echo "BLEND_FILE: $BLEND_FILE" >> /tmp/output.log
echo "BLEND_DIR: $BLEND_DIR" >> /tmp/output.log
echo "START: $START" >> /tmp/output.log
echo "END: $END" >> /tmp/output.log
echo "FORMAT: $FORMAT" >> /tmp/output.log
echo "JOB_ID: $JOB_ID" >> /tmp/output.log 

echo "COPY: blender portable" >> /tmp/output.log
aws s3 cp s3://hive-render-config/blender-2.83.12-linux64.tar.xz /tmp/blender.tar.xz &>> /tmp/output.log

echo "EXTRACT: blender portable" >> /tmp/output.log
tar -xvJf /tmp/blender.tar.xz -C /tmp &>> /tmp/output.log

echo "MKDIR: /tmp/render_out" >> /tmp/output.log
export RENDER_OUT=/tmp/render_out
mkdir $RENDER_OUT

echo "COPY: .blend" >> /tmp/output.log
echo "BLEND_DIR: $BLEND_DIR" >> /tmp/output.log
aws s3 cp s3://hive-render-input/$BLEND_DIR /tmp &>> /tmp/output.log

echo "COPY: enable_gpus.py" >> /tmp/output.log
aws s3 cp s3://hive-render-config/enable_gpus.py /tmp

echo "SET: DISPLAY environment variable" >> /tmp/output.log
export DISPLAY=:0

echo "RENDER: executing..." >> /tmp/output.log
/tmp/blender-2.83.12-linux64/blender -P /tmp/enable_gpus.py -b &>> /tmp/output.log
echo "RENDER: COMPLETE!!" >> /tmp/output.log

echo "COPY: Rendered images to s3 output bucket" >> /tmp/output.log
aws s3 cp $RENDER_OUT s3://hive-render-output/$JOB_ID --recursive --exclude "*" --include "*$FORMAT" &>> /tmp/output.log

echo "END" >> /tmp/output.log

shutdown -h now