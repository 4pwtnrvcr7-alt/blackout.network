# BLACKOUT.NETWORK -> Meshtastic alert broadcast: DESIGN ONLY

Status: **design only. Nothing in this patch transmits.** Matt has to approve this plan before anything here is built or sent.
Our server never transmits onto the mesh. Today the only way anything reaches the mesh from this site is a person pressing Send on their own radio (Live Chat / Push to Mesh).

## 1. What would be sent
- Only Wire stories at rank 7 or higher, after the normal scanner and confirmation rules. Single-source "watchlist" items, including the mesh drop-off signal, are **never** broadcast.
- Format is plain UTF-8 and at most 200 bytes, the same limit Push to Mesh uses:
  `BLACKOUT R8 Severe: <headline trimmed> blackout.network/wire/<id>`
  Example (96 bytes): `BLACKOUT R8 Severe: Tornado warning Seminole County until 3:45 PM blackout.network/wire/ab12cd`
- No emojis, no ads, no affiliate links, and no personal data.

## 2. Where it would go: an opt-in channel, never the public default
- A dedicated **secondary channel named `BLKOUT`** with its own random PSK. We would publish it on /mesh/guide as a QR code or meshtastic.org/e/ URL so people can choose to join.
- It would **never** use the default primary LongFast channel. Automated traffic on a shared default channel is poor etiquette, and the docs already warn that LongFast is congested.
- Messages are sent with `--ch-index <BLKOUT index>`, not as direct messages, with no want-ack and hop limit 3 (the default).

## 3. Hardware and path (recommended option A)
- **A. Matt's own node at home (Sanford), driven locally.** Use a Wi-Fi-capable node such as a Heltec V3 or a RAK4631 with an Ethernet or Wi-Fi module, or a USB-serial node plugged into an always-on Mac or Raspberry Pi.
  - A small script polls the public rank-7+ feed and calls the official Python CLI/API: `meshtastic --host <node> --ch-index N --sendtext "..."`. TCP uses port 4403; serial uses `--port`.
  - The box (cloud) cannot hold a USB radio, so this has to run on hardware at Matt's location. The website and Render never talk to the radio.
- **B. Private MQTT downlink (later, optional).** A broker we run, plus downlink enabled on the BLKOUT channel of Matt's node. This adds broker hosting and a credential to manage, so it is not recommended for v1.
- **Not the public broker (mqtt.meshtastic.org).** Its documented policy is zero-hop for uplinked traffic and "not for sensitive data", and it warns that "further traffic reduction measures may become necessary". It is not a way to inject site-generated broadcasts into other people's meshes, so we do not use it.

## 4. Rate limits and etiquette
- At most 1 message per 15 minutes and 8 per day, with dedupe by story id and by headline similarity.
- Quiet-hours rule: from 11 PM to 7 AM ET, only rank 9+ goes out.
- A kill switch: a file flag on the sending machine. If the flag file exists, nothing sends.
- Log every send locally (time, bytes, story id). No receiving or logging of other users' traffic.
- Respect the duty-cycle and channel-utilization numbers the firmware reports. Skip sending while channel utilization is above 25%.

## 5. FCC and legal (US 915 MHz)
- Meshtastic on 902-928 MHz with a certified LoRa module runs under **FCC Part 15** (unlicensed ISM). That covers automated, encrypted channel traffic, and no call sign is needed. Use stock antennas and power; don't exceed module limits.
- **Ham mode (Part 97) is not used.** It forbids encryption, requires call-sign ID, and bars commercial or "pecuniary interest" content. Links to an ad- or sponsor-supported site could fall under that bar.
- The broadcast is informational, not an official emergency alert. Each message links to the source story, and /mesh/guide would state that it is not an Emergency Alert System or NWS product.

## 6. Cost
- Node: about $25-60 (Heltec V3 or T-Beam), or about $40-120 (RAK WisBlock starter, Station G2).
- Antenna and roof or attic mount: about $20-60. Optional solar relay: about $60-150.
- Software: free (official Python CLI, GPL-3.0). No new hosting for option A.

## 7. Approval checklist for Matt
1. Approve option A, B, or neither.
2. Approve the channel name and PSK publication.
3. Approve the rank threshold (7+), the limits in section 4, and the message format.
4. Name the hardware owner and location.

Once approved, the sender script is a separate patch, tested first on a private test channel.

Sources: meshtastic.org/docs/software/python/cli/, /docs/development/device/client-api/ (TCP 4403), /docs/software/integrations/mqtt/ (public broker policy), /docs/overview/radio-settings/ and /docs/configuration/radio/lora/ (US 915), /docs/faq/ (ham mode and encryption).
