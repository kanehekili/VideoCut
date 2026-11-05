"""mpv construction in the GL path must survive a GL stack that cannot serve us.

initPlayer (the wid path) has always had a try/except that falls back along the
vo chain gpu,xv,x11. initGLPlayer had none, so a machine without a usable GL
stack died with a traceback. It cannot use a vo chain: the render context only
receives frames from vo=libmpv, and any other vo would open a window of its own.
So the fallback switches the GL mode instead, with the two options tweakVirtual
would otherwise apply after construction.

Plain unittest, offscreen Qt, nothing installed beyond what VideoCut needs:

    cd /home/matze/git/VideoCut && python3 -m unittest discover -s tests
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import MpvPlayer  # noqa: E402


def noNvidia():
    """/proc/driver/nvidia/version must not decide the outcome of a test"""
    return mock.patch.object(MpvPlayer.GPUTools, 'hasNvidiaDriver', return_value=False)


def withNvidia():
    return mock.patch.object(MpvPlayer.GPUTools, 'hasNvidiaDriver', return_value=True)


class MpvInitFallbackTest(unittest.TestCase):

    def setUp(self):
        self.player = MpvPlayer.MpvPlayer()
        # _hookEvents parses the real mpv version string; a MagicMock is not one
        patcher = mock.patch.object(MpvPlayer.MpvPlayer, 'mpvVersion', return_value='0.41.0')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_normalStartNeedsNoFallback(self):
        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV') as MPV:
            self.player.initGLPlayer()
            args = MPV.call_args.kwargs
        self.assertEqual(MPV.call_count, 1)
        self.assertEqual(args.get('vo'), 'libmpv')
        self.assertNotIn('gpu-dumb-mode', args, 'software rendering only on retry')

    def test_failureRetriesWithSoftwareRendering(self):
        made = []

        def fake(**kw):
            made.append(kw)
            if len(made) == 1:
                raise RuntimeError('no GL here')
            return mock.MagicMock()

        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV', side_effect=fake):
            self.assertIsNotNone(self.player.initGLPlayer())
        self.assertEqual(len(made), 2, 'exactly one retry')
        self.assertNotIn('gpu-dumb-mode', made[0])
        self.assertEqual(made[1].get('gpu-dumb-mode'), 'yes')
        self.assertEqual(made[1].get('vd-lavc-dr'), 'no')

    def test_voIsNeverChangedByTheFallback(self):
        """the wid path may chain gpu,xv,x11 - the render context may not"""
        made = []

        def fake(**kw):
            made.append(kw)
            if len(made) == 1:
                raise RuntimeError('no GL here')
            return mock.MagicMock()

        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV', side_effect=fake):
            self.player.initGLPlayer()
        for attempt in made:
            self.assertEqual(attempt.get('vo'), 'libmpv')

    def test_failureInSoftwareModeIsNotSwallowed(self):
        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV', side_effect=RuntimeError('hopeless')) as MPV:
            with self.assertRaises(RuntimeError):
                self.player.initGLPlayer()
        self.assertEqual(MPV.call_count, 2, 'one retry, then give up honestly')

    def test_nvidiaStillGetsNvdec(self):
        with withNvidia(), mock.patch.object(MpvPlayer, 'MPV') as MPV:
            self.player.initGLPlayer()
            args = MPV.call_args.kwargs
        self.assertEqual(args.get('hwdec'), 'nvdec_copy')


if __name__ == '__main__':
    unittest.main()
