"""
Udiskie CLI logic.
"""
__all__ = ['mount_options', 'mount', 'umount_options', 'umount']

import warnings
warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)

import os
import logging
import dbus

import udiskie.mount
import udiskie.umount
import udiskie.device
import udiskie.prompt
import udiskie.notify
import udiskie.automount
import udiskie.daemon


def mount_options():
    """
    Return the mount option parser for the mount command.
    """
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='mount all present devices')
    parser.add_option('-v', '--verbose', action='store_const',
                      dest='log_level', default=logging.INFO,
                      const=logging.DEBUG, help='verbose output')
    parser.add_option('-f', '--filters', action='store',
                      dest='filters', default=None,
                      metavar='FILE', help='filter FILE')
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    parser.add_option('-P', '--password-prompt', action='store',
                      dest='password_prompt', default='zenity',
                      metavar='MODULE', help="replace password prompt")
    return parser


def mount(args, allow_daemon=False):
    """
    Execute the mount/daemon command.
    """
    parser = mount_options()
    options, posargs = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')
    run_daemon = allow_daemon and not options.all and len(posargs) == 0

    # establish connection to system bus
    if run_daemon:
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # create a mounter
    prompt = udiskie.prompt.password(options.password_prompt)
    mounter = udiskie.mount.Mounter(
            bus=bus, filter_file=options.filters, prompt=prompt)

    # run udiskie daemon if needed
    if run_daemon:
        daemon = udiskie.daemon.Daemon(bus)
    if run_daemon and not options.suppress_notify:
        notify = udiskie.notify.Notify('udiskie.mount')
        notify.connect(daemon)
    if run_daemon:
        automount = udiskie.automount.AutoMounter(mounter)
        automount.connect(daemon)

    # mount all present devices
    if options.all:
        mounter.mount_present_devices()

    # only mount the desired devices
    elif len(posargs) > 0:
        for path in posargs:
            device = udiskie.device.get_device(mounter.bus, path)
            if device:
                mounter.add_device(device)

    # run in daemon mode
    elif run_daemon:
        mounter.mount_present_devices()
        return daemon.run()

    # print command line options
    else:
        parser.print_usage()



def umount_options():
    """
    Return the command line option parser for the umount command.
    """
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='all devices')
    parser.add_option('-v', '--verbose', action='store_const',
                      dest='log_level', default=logging.INFO,
                      const=logging.DEBUG, help='verbose output')
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    return parser

def umount(args):
    """
    Execute the umount command.
    """
    logger = logging.getLogger('udiskie.umount.cli')
    (options, posargs) = umount_options().parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')

    if options.all:
        unmounted = udiskie.umount.unmount_all()
    else:
        if len(posargs) == 0:
            logger.warn('No devices provided for unmount')
            return 1

        unmounted = []
        for path in posargs:
            device = udiskie.umount.unmount(os.path.normpath(path))
            if device:
                unmounted.append(device)

    # automatically lock unused luks slaves of unmounted devices
    for device in unmounted:
        udiskie.umount.lock_slave(device)
