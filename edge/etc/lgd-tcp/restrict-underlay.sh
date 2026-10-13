#!/bin/sh
set -eu
iptables -N LGD_TCP_UNDERLAY 2>/dev/null || true
iptables -F LGD_TCP_UNDERLAY
iptables -A LGD_TCP_UNDERLAY -p udp -j ACCEPT
iptables -A LGD_TCP_UNDERLAY -p icmp -j ACCEPT
iptables -A LGD_TCP_UNDERLAY -j DROP
iptables -C INPUT -i lgdtcp0 -j LGD_TCP_UNDERLAY 2>/dev/null || iptables -I INPUT 1 -i lgdtcp0 -j LGD_TCP_UNDERLAY
iptables -C FORWARD -i lgdtcp0 -j DROP 2>/dev/null || iptables -I FORWARD 1 -i lgdtcp0 -j DROP
ip6tables -C INPUT -i lgdtcp0 -j DROP 2>/dev/null || ip6tables -I INPUT 1 -i lgdtcp0 -j DROP
ip6tables -C FORWARD -i lgdtcp0 -j DROP 2>/dev/null || ip6tables -I FORWARD 1 -i lgdtcp0 -j DROP
