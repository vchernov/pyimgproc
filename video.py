#!/usr/bin/env python

import os
import sys

import gobject

gobject.threads_init()

import pygst

pygst.require('0.10')
import gst

import pygtk

pygtk.require('2.0')
import gtk

import numpy as np

from matplotlib import pyplot as plt
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas

import imgop


class Player:
    """ Video handler. """

    def __init__(self, fn):
        assert os.path.exists(fn)

        self.frame = None
        self.new_frame_callbacks = set()

        self.mime = ''
        self.width = 0
        self.height = 0

        self.filesrc = gst.element_factory_make('filesrc')
        self.filesrc.set_property('location', fn)

        decoder = gst.element_factory_make('decodebin2')

        videosink = gst.element_factory_make('autovideosink')

        appsink = gst.element_factory_make('appsink')
        appsink.set_property('emit-signals', True)
        appsink.set_property('sync', True)
        appsink.connect('new-buffer', self.on_new_buffer)
        appsink.connect('new-preroll', self.on_new_preroll)

        tee = gst.element_factory_make('tee')
        q1 = gst.element_factory_make('queue')
        q2 = gst.element_factory_make('queue')

        colorspace = gst.element_factory_make("ffmpegcolorspace")
        capsfilter = gst.element_factory_make("capsfilter")
        capsfilter.set_property("caps", gst.Caps("video/x-raw-rgb"))

        self.pipe = gst.Pipeline()
        self.pipe.add(self.filesrc, decoder, tee)
        self.pipe.add(q1, videosink)
        self.pipe.add(q2, colorspace, capsfilter, appsink)

        def on_pad_added(obj, pad, target):
            sinkpad = target.get_compatible_pad(pad, pad.get_caps())
            if sinkpad:
                pad.link(sinkpad)

        decoder.connect('pad-added', on_pad_added, tee)

        gst.element_link_many(self.filesrc, decoder)
        gst.element_link_many(tee, q1, videosink)
        gst.element_link_many(tee, q2, colorspace, capsfilter, appsink)

        bus = self.pipe.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)

        self.pipe.set_state(gst.STATE_PAUSED)
        self.pipe.get_state()

    def on_message(self, bus, msg):
        if msg.type == gst.MESSAGE_EOS:
            self.seek(0)
        elif msg.type == gst.MESSAGE_ERROR:
            err, debug = msg.parse_error()
            print err, debug
            halt()

    def play(self):
        self.pipe.set_state(gst.STATE_PLAYING)

    def pause(self):
        self.pipe.set_state(gst.STATE_PAUSED)

    def seek(self, position):
        self.pipe.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, position)

    def duration(self):
        return self.pipe.query_duration(gst.FORMAT_TIME, None)[0]

    def position(self):
        return self.pipe.query_position(gst.FORMAT_TIME, None)[0]

    def on_new_preroll(self, appsink):
        buf = appsink.emit('pull-preroll')

        struct = buf.caps[0]
        self.mime = struct.get_name()
        self.width = struct['width']
        self.height = struct['height']

        assert self.mime == 'video/x-raw-rgb'
        assert len(buf) == self.width * self.height * 3

        self.grab_frame(buf)

    def on_new_buffer(self, appsink):
        buf = appsink.emit('pull-buffer')
        self.grab_frame(buf)

    def grab_frame(self, buf):
        if self.frame is None:
            self.frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        pixels = np.frombuffer(buf.data, dtype=np.uint8)
        buf_len = len(buf)
        assert pixels.shape[0] == buf_len

        size = (self.height, self.width)
        self.frame[:, :, 0] = pixels[0:buf_len:3].reshape(size)
        self.frame[:, :, 1] = pixels[1:buf_len:3].reshape(size)
        self.frame[:, :, 2] = pixels[2:buf_len:3].reshape(size)

        for callback in self.new_frame_callbacks:
            callback(self)

    def location(self):
        return self.filesrc.get_property('location')

    def save(self, fn):
        if self.frame is not None:
            imgop.save_image(self.frame, fn)

    def generate_screenshot_name(self):
        location = self.location()
        timestamp = self.position()
        return "%s-%s" % (os.path.basename(location), str(timestamp))


class PlayerGui:
    """ Control panel. """

    def __init__(self, player, actions=None):
        self.player = player
        if not actions:
            actions = {}

        self.wnd = gtk.Window()
        self.wnd.set_position(gtk.WIN_POS_CENTER)
        self.wnd.set_default_size(480, -1)
        self.wnd.connect('destroy', lambda w: halt())
        self.wnd.set_border_width(10)

        location = self.player.location()
        fn = os.path.basename(location)
        self.wnd.set_title(fn)

        main_box = gtk.VBox(False, 10)
        self.wnd.add(main_box)

        ctrl_box = gtk.HBox(False, 5)
        main_box.pack_start(ctrl_box, False, False, 0)

        play_icon = gtk.Image()
        play_icon.set_from_stock(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_BUTTON)
        play_btn = gtk.Button()
        play_btn.set_image(play_icon)
        play_btn.connect('clicked', self.on_play)
        ctrl_box.pack_start(play_btn, False, False, 0)

        pause_icon = gtk.Image()
        pause_icon.set_from_stock(gtk.STOCK_MEDIA_PAUSE, gtk.ICON_SIZE_BUTTON)
        pause_btn = gtk.Button()
        pause_btn.set_image(pause_icon)
        pause_btn.connect('clicked', self.on_pause)
        ctrl_box.pack_start(pause_btn, False, False, 0)

        self.slider_adj = gtk.Adjustment(value=0, lower=0, upper=player.duration())
        self.slider = gtk.HScale(self.slider_adj)
        self.slider.set_draw_value(True)
        self.slider.set_value_pos(gtk.POS_RIGHT)
        self.slider.set_update_policy(gtk.UPDATE_DELAYED)
        self.slider_signal_id = self.slider.connect('value-changed', self.on_slide)
        self.slider.connect('format-value', self.on_format_value)
        ctrl_box.pack_start(self.slider, True, True, 0)

        screenshot_icon = gtk.Image()
        screenshot_icon.set_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_BUTTON)
        screenshot_btn = gtk.Button()
        screenshot_btn.set_image(screenshot_icon)
        screenshot_btn.connect('clicked', self.on_screenshot)
        ctrl_box.pack_start(screenshot_btn, False, False, 0)

        action_box = gtk.VBox(False, 5)
        main_box.pack_start(action_box, False, False, 0)
        for name, cmd in actions.iteritems():
            box = gtk.HBox(False, 0)
            action_box.pack_start(box, False, False, 0)
            btn = gtk.Button(name)
            btn.connect('clicked', self.on_action, cmd)
            box.pack_start(btn, False, False, 0)

        self.wnd.show_all()

        self.player.new_frame_callbacks.add(self.on_new_frame)

    def on_play(self, widget):
        self.player.play()

    def on_pause(self, widget):
        self.player.pause()

    def on_slide(self, widget):
        position = int(widget.get_value())
        self.player.seek(position)

    def on_format_value(self, widget, value):
        duration = self.player.duration()
        return '%s / %s' % (ns2str(int(value)), ns2str(duration))

    def on_new_frame(self, player):
        self.slider.handler_block(self.slider_signal_id)
        self.slider_adj.set_value(player.position())
        self.slider.handler_unblock(self.slider_signal_id)

    def on_screenshot(self, widget):
        default_name = self.player.generate_screenshot_name() + '.jpg'
        default_folder = os.path.dirname(self.player.location())

        dialog = gtk.FileChooserDialog("Save screenshot", self.wnd,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_current_name(default_name)
        dialog.set_current_folder(default_folder)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fn = dialog.get_filename()
            self.player.save(fn)
        dialog.destroy()

    def on_action(self, widget, command):
        command.execute(self.player)


def ns2str(t):
    """ Converts nanoseconds to string. """
    s, ns = divmod(t, gst.SECOND)
    m, s = divmod(s, 60)
    if m < 60:
        return "%02i:%02i" % (m, s)
    else:
        h, m = divmod(m, 60)
        return "%i:%02i:%02i" % (h, m, s)


class BlankFigure:
    """ Base class for figures. """

    def __init__(self, title, size):
        self.wnd = None
        self.title = title
        self.size = size
        self.fig = None

    def show(self):
        if self.visible():
            return

        self.wnd = gtk.Window()
        self.wnd.connect('destroy', self.on_destroy)
        self.wnd.move(0, 0)
        self.wnd.set_default_size(self.size[0], self.size[1])
        self.wnd.set_title(self.title)

        self.fig = plt.figure()
        canvas = FigureCanvas(self.fig)
        self.wnd.add(canvas)

        self.wnd.show_all()

    def hide(self):
        if not self.visible():
            return
        self.wnd.destroy()

    def visible(self):
        return self.wnd is not None

    def on_destroy(self, widget):
        self.wnd = None
        self.fig = None

    def draw_begin(self):
        self.show()
        self.fig.clear()

    def draw_end(self):
        self.fig.canvas.draw()


class HistRgb(BlankFigure):
    """ RGB histogram. """

    def __init__(self):
        BlankFigure.__init__(self, 'RGB histogram', (400, 500))

    def draw(self, frame):
        self.draw_begin()

        self.histogram(frame[:, :, 0], 311, 'r')
        self.histogram(frame[:, :, 1], 312, 'g')
        self.histogram(frame[:, :, 2], 313, 'b')

        self.draw_end()

    def histogram(self, channel, place, bin_color):
        ax = self.fig.add_subplot(place)
        ax.hist(channel.ravel(), 256, [0, 255], color=bin_color)
        ax.get_yaxis().set_visible(False)
        plt.xlim([0, 256])


class ShowFigureAction:
    def __init__(self, figure):
        self.figure = figure

    def execute(self, player):
        self.figure.draw(player.frame)


def show(fn, actions=None):
    if not actions:
        actions = {}
    player = Player(fn)
    PlayerGui(player, actions)
    run()


def run():
    gtk.main()


def halt():
    gtk.main_quit()


if __name__ == '__main__':
    if len(sys.argv) == 2:
        show(sys.argv[1])
    else:
        print 'usage: %s video_file' % sys.argv[0]
