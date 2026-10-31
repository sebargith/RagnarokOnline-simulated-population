import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PERL = ROOT.parent / 'vendor/strawberry-perl/perl/bin/perl.exe'
SCRIPT = r'''
use JSON::PP;
use M1Healing;
my $path = $ARGV[0];
my $h = M1Healing->new($path);
my $ctx = sub { my %o = @_; return {ready => 1, dead => 0, busy => 0, threat => 0,
    phase => 'rest', hp => 20, hp_max => 50, name_id => 512, type => 0,
    equipped => 0, amount => 2, index => '0100', %o} };
my %admit = (ok => $h->eligible($ctx->(), 100));
for my $case ([healthy => hp => 50], [boundary => hp => 30], [dead => dead => 1],
    [busy => busy => 1], [threat => threat => 1], [not_ready => ready => 0],
    [not_rest => phase => 'retreat'], [other_item => name_id => 601],
    [other_type => type => 2], [equipped => equipped => 1], [empty => amount => 0]) {
    my ($name, $key, $value) = @$case;
    $admit{$name} = $h->eligible($ctx->($key => $value), 100);
}
my $began = $h->begin($ctx->(), 100);
my $restarted = M1Healing->new($path);
my $restart = [$restarted->state->{status}, $restarted->begin($ctx->(), 200)];
my $ack = sub { my %o = @_; return {own => 1, index => '0100', name_id => 512,
    success => 1, remaining => 1, %o} };
my @ignored = map { $h->observe($_) } ($ack->(own => 0), $ack->(index => '0200'), $ack->(name_id => 513));
my $confirmed = $h->observe($ack->());
my $state = {%{$h->state}};
my $cooldown = [$h->eligible($ctx->(), 109), $h->eligible($ctx->(), 110)];
$h->begin($ctx->(), 110);
my $expires = [$h->expire(114), $h->expire(115), $h->begin($ctx->(), 200)];
my $unknown = M1Healing->new($path)->state->{status};
my $failed = M1Healing->new($path . '-failed');
$failed->begin($ctx->(), 100); $failed->observe($ack->(success => 0));
my $fail_state = [$failed->state->{status}, $failed->begin($ctx->(), 200)];
my $mismatch = M1Healing->new($path . '-mismatch');
$mismatch->begin($ctx->(), 100); $mismatch->observe($ack->(remaining => 0));
my $badpath = M1Healing->new($path . '/missing');
my $iofail = [$badpath->begin($ctx->(), 100), $badpath->state->{status}];
open my $f, '>', $path; print {$f} '{broken'; close $f;
my $corrupt = M1Healing->new($path);
print encode_json({admit => \%admit, began => $began, restart => $restart,
    ignored => \@ignored, confirmed => $confirmed, state => $state, cooldown => $cooldown,
    expires => $expires, unknown => $unknown, failed => $fail_state,
    mismatch => $mismatch->state->{status}, iofail => $iofail,
    corrupt => [$corrupt->state->{status}, $corrupt->begin($ctx->(), 200)]});
'''


class HealingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PERL.exists():
            raise unittest.SkipTest('Pinned Perl unavailable')
        with tempfile.TemporaryDirectory() as folder:
            run = subprocess.run([str(PERL), '-I' + str(ROOT/'bridge/lib'), '-e', SCRIPT,
                                  str(Path(folder)/'state.json')], capture_output=True, text=True, timeout=10)
            if run.returncode:
                raise AssertionError(run.stderr)
            cls.data = json.loads(run.stdout)

    def test_only_owned_apple_when_idle_hurt_and_safe(self):
        self.assertEqual(self.data['admit'], {k: int(k == 'ok') for k in self.data['admit']})

    def test_confirmation_matches_own_packet_and_exact_decrement(self):
        self.assertEqual(self.data['ignored'], [0, 0, 0])
        self.assertEqual(self.data['confirmed'], 1)
        self.assertEqual(self.data['state']['status'], 'confirmed')
        self.assertEqual(self.data['mismatch'], 'unknown')

    def test_cooldown_and_timeout_never_resend(self):
        self.assertEqual(self.data['cooldown'], [0, 1])
        self.assertEqual(self.data['expires'], [0, 1, 0])
        self.assertEqual(self.data['unknown'], 'unknown')
        self.assertEqual(self.data['failed'], ['failed', 0])

    def test_restart_and_storage_failure_block_sending(self):
        self.assertEqual(self.data['began'], 1)
        self.assertEqual(self.data['restart'], ['unknown', 0])
        self.assertEqual(self.data['iofail'], [None, 'error'])
        self.assertEqual(self.data['corrupt'], ['error', 0])


if __name__ == '__main__':
    unittest.main()
