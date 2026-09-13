# Design — a mobile unit that reports, and that nothing outside can move

**Status:** settled, and narrower than it started. The owner decided that the
house triggers the robot itself — after the litter box finishes its own
cleaning cycle, within 09:00–18:00, and a night visit becomes one run at 09:00.
The lab receives **telemetry only**. The command channel described below was
built, reviewed, and then retired without ever being used (D-056).

The lab has a role, `tag:drone`, for a unit that both reports and takes
commands. It has never had a device, and after this decision it still does not:
the robot is not on the tailnet, and nothing outside the house can move it.
That is a stronger sentence than the one this design started with, and it cost
a working feature to get.

---

## What the vacuum is, factually

Checked on the hub by the session that manages the house, not assumed:

- **It cannot run a tailnet client.** It is a vendor appliance.
- **Its control path already leaves the house.** The hub reaches it through the
  vendor's cloud, not over the home network: hub → vendor cloud → robot,
  measured at about 20 seconds from command to movement.
- **The hub can command a lot**: start, pause, stop, return to dock, spot and
  area cleaning, five named vendor scenarios, fan speed, water level, cleaning
  mode, do-not-disturb, child lock, auto-empty, map deletion, and a raw
  passthrough command.
- **It reports plenty**: state, battery, task and dock status, errors, current
  and lifetime cleaning area and time, and consumable hours.

## What the lab gets, and what it does not

**Telemetry, pushed by the hub**, exactly like the outdoor temperature: state,
battery, task and dock status, errors, cleaning area and time, and consumables.
On change, and on the five-minute tick at second 45.

**Never pushed:** the map image, the robot's coordinates, the network details.
A floor plan and a position inside the flat have no place on a public page, and
the lab has no use for them.

**No command path at all.** Not a guarded one, not a narrow one. The trigger
lives in the house: the litter box finishes its cycle, the house's own
automation decides, and the robot tidies the area. The collector cannot ask,
because there is nothing to ask.

## Why the built channel was retired rather than kept "just in case"

The channel worked. `GET /command` on the collector answered `{}` or one queued
name, handed over once; the hub asked on its own tick; the allowlist and every
guard lived in the hub. It was reviewed against the hub, and the review found a
real gap in it — an operator could re-queue the one allowed command every five
minutes and keep the robot running all day at the cat's bowls — which was fixed
with a three-hour cooldown.

Then the owner chose a design where the house does not need to be asked. That
makes the endpoint unused, and an unused endpoint is not free: it is a path
that exists, that someone must remember, and whose guards must keep working for
a caller that never calls. So it was removed from the receiver, the operator's
queue script was deleted, and the allowlist is empty because there is no list.

What survives is the reasoning, kept below, because the alternatives are the
argument: the two shapes that were refused for widening the house's exposure,
and the one that was built and then judged unnecessary.

## The invariant the whole design was built around

The collector lives outside the house. It has no path into the house, by policy
and by test (D-049). Every shape considered had to keep that true:

| shape | why not |
|---|---|
| a webhook on the hub | needs `collector → hub:8123`, the widening the telemetry design was built to avoid; and a webhook id is a bearer secret |
| an MQTT topic on the house broker | needs `collector → hub:1883`, and that broker's access list is not enforced — every login is effectively a superuser (D-048) |
| the hub asks the collector | kept the invariant, was built and reviewed — and then made unnecessary by a house-side trigger |
| the house decides for itself | what was chosen: no channel, nothing to guard, nothing to ask |

## Publishing

Counts of runs only, if anything: no times, no sequence. A timeline of when the
robot cleaned the cat's area is a timeline of when the cat used it and when the
flat was empty. The command-outcome buckets that an earlier version of this
document proposed no longer exist, because the commands do not.

## Kept for the record: the channel as it was reviewed

The first draft was written from the household session's facts; it reviewed it
against the hub and corrected six things. The corrections are the interesting
part, so they are kept here rather than quietly folded in.

**A safety gap I had missed.** One command, handed over once, still lets an
operator queue it again every five minutes: the robot would clean the cat's
area, dock, and set off again, all day. My draft counted starts in a helper.
The house's answer is better and needs no helper: require the vacuum to have
been **docked, unchanged, for three hours**. That caps lab starts at about four
a day inside the window, refuses a lab start stacking on a clean the household
just ran, and refuses automatically when the vendor cloud flaps — because an
`unavailable` resets the clock.

**The failure I wrote in.** My template read `reply.content` unguarded. When
the poll times out, `continue_on_error` lets the run continue and the variable
is never set, so the automation would have failed every five minutes for as
long as the collector was down — turning our outage into their noise. It now
checks `reply is defined and reply.status == 200 and reply.content is mapping`.

**Do not call the household's script.** I had reused `script.vacuum_pet_litter`,
which is the button in the house's own app. It has been repointed once already,
and if it is repointed again the lab's command silently becomes something else.
The corrected version selects the scenario itself, matched by name prefix, and
refuses with `no_scenario` if the option is missing.

**Waiting long enough to mean it.** "Accepted" only meant the hub pressed a
button in the vendor's cloud. It now waits up to 90 seconds for the vacuum to
report `cleaning` and answers `started` or `sent_no_start`.

**Two small ones:** the poll runs at second 30 so it never shares an instant
with the temperature push, and the automation is `max_exceeded: silent`.

**Stops are not needed after all.** I was going to put pause and return-to-dock
to the owner as safety. The house already keeps its own stops — the vendor app
and the wall tablet — so adding them to the lab's list buys nothing and widens
it. The allowlist stays at one command.

**What may be published.** Three counts only: started, refused by a house
guard, and not on the allowlist. The per-guard reasons stay in the collector's
own log: published over time, a `cat_not_clear` count is a count of how often
the cat was at his bowls, which is the household's business and not the
reader's.

### The corrected draft, never applied

Reviewed against the hub by the household session, which applies it after the
owner approves there. The one allowed command and every guard live in this
file, on the hub — not in the lab.

```yaml
# secrets.yaml
zt_collector_command_url: "http://<collector tailnet address>/command"

# configuration.yaml, under the existing rest_command block
  zt_lab_ask_command:
    url: !secret zt_collector_command_url
    method: GET
    timeout: 5

  zt_lab_push_command_outcome:
    url: !secret zt_collector_ingest_url
    method: POST
    content_type: "application/json"
    timeout: 5
    payload: >-
      {"sensor":"vacuum_command_outcome","value":{{ outcome | tojson }},
       "reason":{{ reason | tojson }},"id":{{ id | tojson }},
       "ts":"{{ now().isoformat() }}"}
```

```yaml
# automations.yaml
- id: zt_lab_vacuum_ask
  alias: "zero-trust-lab: ask the collector for a vacuum command"
  description: "Lab mobile-unit channel. The hub asks; the one allowed command and every guard live here, not in the lab."
  mode: single
  max_exceeded: silent
  triggers:
    - trigger: time_pattern
      minutes: "/5"
      seconds: 30
  actions:
    - action: rest_command.zt_lab_ask_command
      response_variable: reply
      continue_on_error: true
    - variables:
        body: "{{ reply.content if (reply is defined and reply.status == 200 and reply.content is mapping) else {} }}"
        cmd: "{{ body.command | default('', true) }}"
        cmd_id: "{{ body.id | default('', true) }}"
    - condition: template
      value_template: "{{ cmd != '' }}"
    - variables:
        reason: >-
          {%- set occ = states.binary_sensor.cat_cam_cat_occupancy -%}
          {%- set vac = states.vacuum.eufy_ae_c10 -%}
          {%- set opts = state_attr('select.eufy_ae_c10_scene_task','options') | default([], true) | select('search','^Pet Litter Light') | list -%}
          {%- if cmd != 'pet_area_light' -%}not_allowlisted
          {%- elif occ is none or occ.state != 'off' or (now() - occ.last_changed).total_seconds() < 600 -%}cat_not_clear
          {%- elif vac is none or vac.state != 'docked' -%}not_docked
          {%- elif (now() - vac.last_changed).total_seconds() < 10800 -%}cooldown
          {%- elif states('sensor.eufy_ae_c10_battery') | float(0) < 50 -%}battery
          {%- elif states('sensor.eufy_ae_c10_error_message') not in ['', 'unknown'] -%}robot_error
          {%- elif not (today_at('08:00') <= now() < today_at('20:30')) -%}quiet_hours
          {%- elif opts | count == 0 -%}no_scenario
          {%- else -%}ok{%- endif -%}
    - if:
        - condition: template
          value_template: "{{ reason == 'ok' }}"
      then:
        - action: select.select_option
          target:
            entity_id: select.eufy_ae_c10_scene_task
          data:
            option: "{{ state_attr('select.eufy_ae_c10_scene_task','options') | select('search','^Pet Litter Light') | list | first }}"
        - wait_for_trigger:
            - trigger: state
              entity_id: vacuum.eufy_ae_c10
              to: cleaning
          timeout: "00:01:30"
          continue_on_timeout: true
        - action: rest_command.zt_lab_push_command_outcome
          data:
            outcome: "{{ 'started' if wait.trigger else 'sent_no_start' }}"
            reason: ""
            id: "{{ cmd_id }}"
          continue_on_error: true
      else:
        - action: rest_command.zt_lab_push_command_outcome
          data:
            outcome: refused
            reason: "{{ reason }}"
            id: "{{ cmd_id }}"
          continue_on_error: true
```

The guards, in words: the cat has been out of frame for ten minutes and the
sensor is not merely unavailable; the vacuum is docked and has been for three
hours; the battery is at least half; the robot reports no error; the local time
is between 08:00 and 20:30, so a ten-to-fifteen minute clean finishes before
the robot's own quiet hours begin; and the scenario still exists under the name
the automation matches.

Telemetry — state, battery, task and dock status, errors, cleaning area and
time, consumables — is pushed the same way the temperature is, on change and on
the five-minute tick at second 45. Three jobs now share that tick: the
temperature push, this one, and the ask at second 30. They are spread across
the minute deliberately, and while the collector is down each logs one error
per tick on the hub — a cost the household session accepted and wrote into the
house's own records. Never pushed:
the map image, the robot's coordinates, the network details. A floor plan and a
position inside the flat have no place on a public page.

### One helper, and why not two

`input_text.zt_lab_last_command_id` remembers the last id handled, so a
repeated id does nothing. It is a second belt: the collector already hands a
command over once. A daily counter was considered and dropped — the cooldown
caps starts at about four a day on its own, and a helper that has to be reset
at midnight, and restored after a restart, is a moving part earning very
little.

### The order the first commands would have run in

1. An idle poll returns `{}`, and the household session confirms the response
   shape from the hub's own trace.
2. An unknown name: refused, `not_allowlisted`. Nothing moves.
3. The real name at a moment a guard is certain to fail — after 20:30, so
   `quiet_hours`. Nothing moves.
4. Only then a real start, in hours, with the household told first, and the
   camera-watching session warned that the robot will be in frame.

Refusals before motion is the right order, and it is the household session's
condition, not a courtesy.

### Delivery: at most once, on purpose

The collector hands a command over as it is served and forgets it. If the
reply is lost, the command is lost and the operator queues it again; the
alternative -- keep serving until acknowledged -- turns a lost acknowledgement
into a second clean. The hub's memory of the last id stays as a second belt:
two mechanisms, both cheap, and the failure mode of each is that nothing moves.

### One command, settled

The household session first proposed four names; the owner named one. The stops
turned out to be unnecessary — the house keeps its own, in the vendor's app and
on the wall tablet — so the list stays at the cat-area light clean, and every
other name is answered `not_allowlisted` without anything moving.
