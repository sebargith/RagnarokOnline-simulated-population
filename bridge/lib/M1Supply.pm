package M1Supply;
use strict;
use warnings;
use M1Navigation;

# Pure contract for P2b: bounded selling of loot to and buying from NPC shops.
# The plugin supplies observed state (inventory, server price lists); nothing
# here touches the network or game globals.
use constant {MIN_TIMEOUT => 5, MAX_TIMEOUT => 60, RANGE => 5, MAX_LINES => 8,
    ETC => 3, MAX_WEIGHT_PERCENT => 50};

my %KEYS = (npc_sell => 'items,timeout_s,type,x,y', npc_buy => 'items,max_zeny,timeout_s,type,x,y');

sub _shape {
    my ($a) = @_;
    return 0 unless join(',', sort keys %$a) eq ($KEYS{$a->{type} // ''} // '') &&
        !grep { !defined($a->{$_}) || ref($a->{$_}) } qw(timeout_s x y);
    return 0 unless $a->{x} =~ /^\d{1,3}$/ && $a->{y} =~ /^\d{1,3}$/ && $a->{timeout_s} =~ /^\d{1,3}$/;
    return 0 if $a->{type} eq 'npc_buy' && (ref($a->{max_zeny}) || $a->{max_zeny} !~ /^\d{1,9}$/);
    return 0 unless ref($a->{items}) eq 'ARRAY' && @{$a->{items}} >= 1 && @{$a->{items}} <= MAX_LINES;
    my %ids;
    for my $i (@{$a->{items}}) {
        return 0 unless ref($i) eq 'HASH' && join(',', sort keys %$i) eq 'amount,name_id' &&
            !ref($i->{amount}) && !ref($i->{name_id}) && ($i->{amount} // '') =~ /^[1-9]\d{0,2}$/ &&
            ($i->{name_id} // '') =~ /^[1-9]\d{0,5}$/ && !$ids{$i->{name_id}}++;
    }
    1;
}

sub _common {
    my ($a, $ctx) = @_;
    return 'invalid_timeout' if $a->{timeout_s} < MIN_TIMEOUT || $a->{timeout_s} > MAX_TIMEOUT;
    return 'executor_not_native' unless $ctx->{manual_ai};
    return 'dead' unless $ctx->{hp} > 0;
    return 'recovering' if $ctx->{recovering};
    return 'already_talking' if $ctx->{talking};
    return 'npc_not_found' unless $ctx->{npc};
    return 'npc_too_far' if M1Navigation::distance($ctx->{npc}, $ctx->{pos}) > RANGE;
    undef;
}

# $ctx->{inventory}: [{name_id, amount, type, equipped}] as observed.
sub validate_sell {
    my ($a, $ctx) = @_;
    return 'invalid_npc_sell' unless ($a->{type} // '') eq 'npc_sell' && _shape($a);
    my $r = _common($a, $ctx);
    return $r if $r;
    for my $i (@{$a->{items}}) {
        my @held = grep { $_->{name_id} == $i->{name_id} } @{$ctx->{inventory}};
        # Only unequipped loot (etc) is sold; equipment and consumables are kept.
        return 'item_not_sellable' if grep { $_->{equipped} || $_->{type} != ETC } @held;
        my $have = 0; $have += $_->{amount} for @held;
        return 'insufficient_amount' if $have < $i->{amount};
    }
    undef;
}

sub validate_buy {
    my ($a, $ctx) = @_;
    return 'invalid_npc_buy' unless ($a->{type} // '') eq 'npc_buy' && _shape($a);
    my $r = _common($a, $ctx);
    return $r if $r;
    # A budget can only be money the character actually has.
    return 'insufficient_zeny' if $a->{max_zeny} > $ctx->{zeny} || $ctx->{zeny} <= 0;
    undef;
}

# $offers: {name_id => price each} from the server's sell list.
# Returns (undef, expected_zeny) or ('not_in_sell_list').
sub sell_quote {
    my ($items, $offers) = @_;
    my $total = 0;
    for my $i (@$items) {
        return ('not_in_sell_list') unless defined $offers->{$i->{name_id}};
        $total += $offers->{$i->{name_id}} * $i->{amount};
    }
    (undef, $total);
}

# $store: {name_id => price} from the server's buy list; weights in tenths
# (item_weights.txt), character weight in whole units as OpenKore stores it.
# Returns (undef, cost) or (reason). Nothing is sent when a reason is returned.
sub buy_quote {
    my ($items, $store, $o) = @_;
    my ($cost, $added) = (0, 0);
    for my $i (@$items) {
        return ('not_in_store') unless defined $store->{$i->{name_id}};
        $cost += $store->{$i->{name_id}} * $i->{amount};
        $added += ($o->{item_weight}{$i->{name_id}} // 0) * $i->{amount} / 10;
    }
    return ('over_budget') if $cost > $o->{max_zeny};
    return ('insufficient_zeny') if $cost > $o->{zeny};
    return ('overweight_after_buy') if !$o->{weight_max} ||
        ($o->{weight} + $added) * 100 / $o->{weight_max} >= MAX_WEIGHT_PERCENT;
    (undef, $cost);
}

sub buy_failure {
    my ($code) = @_;
    return ('failed', ('server_insufficient_zeny', 'server_weight', 'server_item_limit',
        'server_not_in_store', 'server_not_exchangeable', 'server_invalid_store')[$code - 1] // 'server_buy_failed');
}

# Compares observed Zeny and per-item amounts with what the trade implies.
# $before/$after: {zeny, items => {name_id => amount}}; $expect: {zeny, items => {name_id => delta}}.
sub reconcile {
    my ($done, $before, $after, $expect) = @_;
    my %delta;
    $delta{$_} = ($after->{items}{$_} // 0) - ($before->{items}{$_} // 0)
        for keys %{{%{$before->{items}}, %{$after->{items}}}};
    my $zeny = $after->{zeny} - $before->{zeny};
    my @off = grep { ($delta{$_} // 0) != ($expect->{items}{$_} // 0) }
        keys %{{%delta, %{$expect->{items}}}};
    my $observed = {zeny => $zeny, items => {map { $_ => $delta{$_} } grep { $delta{$_} } sort keys %delta}};
    return ('completed', $done, $observed) if $zeny == $expect->{zeny} && !@off;
    ('unknown', 'state_mismatch', $observed);
}
1;
