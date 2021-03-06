#!/usr/bin/env python

"""
Train a CNN on CIFAR 100.

Takes about 100 minutes.
"""

from __future__ import print_function
import numpy as np
np.random.seed(0)
import gtsdb
from keras.preprocessing.image import ImageDataGenerator
from keras import backend as K
from keras.optimizers import Adam
from keras.callbacks import ModelCheckpoint
from keras.utils import np_utils
from sklearn.model_selection import train_test_split
import csv
import densenet
import sequential_model

batch_size = 64
nb_classes = gtsdb.n_classes
nb_epoch = 200
data_augmentation = True
load_smoothed_labels = False
model_type = 'dense'

# input image dimensions
img_rows, img_cols = 32, 32
# The CIFAR10 images are RGB.
img_channels = 3

# The data, shuffled and split between train and test sets:
data = gtsdb.load_data()
X_train, y_train = data['x_train'], data['y_train']
X_val, y_val = X_train, y_train
# X_train, X_val, y_train, y_val = train_test_split(X_train, y_train,
#                                                   test_size=0.10,
#                                                   random_state=42)

# Convert class vectors to binary class matrices.
Y_train = np_utils.to_categorical(y_train, nb_classes)
print(Y_train.shape)
# Y_train = Y_train.reshape((-1, 1, 1, nb_classes))  - fully convolutional
print(Y_train.shape)

if load_smoothed_labels:
    Y_train = np.load('smoothed_lables.npy')
Y_val = np_utils.to_categorical(y_val, nb_classes)
# Y_test = np_utils.to_categorical(y_test, nb_classes)

# Input shape depends on the backend
if K.image_dim_ordering() == "th":
    input_shape = (img_channels, img_rows, img_cols)
else:
    input_shape = (img_rows, img_cols, img_channels)

if model_type == 'sequential':
    model = sequential_model.create_model(nb_classes, input_shape)
elif model_type == 'dense':
    depth = 100
    nb_dense_block = 3
    growth_rate = 12
    nb_filter = -1
    bottleneck = True
    reduction = 0.5
    dropout_rate = 0.0  # 0.0 for data augmentation

    model = densenet.create_dense_net(nb_classes, input_shape, depth, nb_dense_block,
                                      growth_rate, nb_filter,
                                      bottleneck=bottleneck, reduction=reduction,
                                      dropout_rate=dropout_rate)
else:
    print("Not implemented model '{}'".format(model_type))
print("Model created")

model.summary()
optimizer = Adam(lr=1e-4)  # Using Adam instead of SGD to speed up training
model.compile(loss='categorical_crossentropy',
              optimizer=optimizer,
              metrics=["accuracy"])
print("Finished compiling")
print("Building model...")

X_train = X_train.astype('float32')
X_val = X_val.astype('float32')
# X_test = X_test.astype('float32')
X_train /= 255
X_val /= 255
# X_test /= 255

if not data_augmentation:
    print('Not using data augmentation.')
    model.fit(X_train, Y_train,
              batch_size=batch_size,
              nb_epoch=nb_epoch,
              validation_data=(X_val, Y_val),
              shuffle=True)
else:
    print('Using real-time data augmentation.')
    # This will do preprocessing and realtime data augmentation:
    datagen = ImageDataGenerator(
        featurewise_center=False,  # set input mean to 0 over the dataset
        samplewise_center=False,  # set each sample mean to 0
        featurewise_std_normalization=False,  # divide inputs by std of the dataset
        samplewise_std_normalization=False,  # divide each input by its std
        zca_whitening=False,  # apply ZCA whitening
        rotation_range=15,  # randomly rotate images in the range (degrees, 0 to 180)
        width_shift_range=5. / 32,  # randomly shift images horizontally (fraction of total width)
        height_shift_range=5. / 32,  # randomly shift images vertically (fraction of total height)
        horizontal_flip=True,  # randomly flip images
        vertical_flip=False)  # randomly flip images

    # Compute quantities required for featurewise normalization
    # (std, mean, and principal components if ZCA whitening is applied).
    datagen.fit(X_train, seed=0)

    # Fit the model on the batches generated by datagen.flow().
    cb = ModelCheckpoint("weights/DenseNet-BC-100-12-gtsdb.h5",
                         monitor="val_acc",
                         save_best_only=True,
                         save_weights_only=False)
    history_callback = model.fit_generator(datagen.flow(X_train, Y_train,
                                           batch_size=batch_size),
                                           samples_per_epoch=X_train.shape[0],
                                           nb_epoch=nb_epoch,
                                           validation_data=(X_train, Y_train),
                                           callbacks=[cb])
    # history_callback = model.fit_generator(gtsdb.ImageDataGenerator(batch_size=batch_size),
    #                                        samples_per_epoch=X_train.shape[0],
    #                                        nb_epoch=nb_epoch,
    #                                        validation_data=(X_val, Y_val),
    #                                        callbacks=[cb])
    loss_history = history_callback.history["loss"]
    acc_history = history_callback.history["acc"]
    val_acc_history = history_callback.history["val_acc"]
    np_loss_history = np.array(loss_history)
    np_acc_history = np.array(acc_history)
    np_val_acc_history = np.array(val_acc_history)
    data = zip(np_loss_history, np_acc_history, np_val_acc_history)
    data = [("%0.4f" % el[0],
             "%0.4f" % el[1],
             "%0.4f" % el[2]) for el in data]
    with open('history.csv', 'w') as fp:
        writer = csv.writer(fp, delimiter=',')
        writer.writerows([("loss", "acc", "val_acc")])
        writer.writerows(data)
model.save('gtsdb.h5')
