import gzip
import xml.etree.ElementTree as ET
import sys
import os
import csv

def decompress_als(file_path):
    output_path = file_path.replace(".als", ".xml")
    with gzip.open(file_path, 'rb') as f_in:
        with open(output_path, 'wb') as f_out:
            f_out.write(f_in.read())
    return output_path

def shorten_path(path):
    if not path:
        return ""
    home = os.path.expanduser("~")
    return path.replace(home, "~")

def extract_track_info(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    tracks = []

    for track_tag in ["AudioTrack", "MidiTrack"]:
        for track in root.findall(f".//{track_tag}"):
            name_node = track.find(".//Name/EffectiveName")
            track_name = name_node.attrib.get("Value") if name_node is not None else "Unnamed"
            clips = []

            clip_tag = "AudioClip" if track_tag == "AudioTrack" else "MidiClip"
            for clip in track.findall(f".//{clip_tag}"):
                clip_name_node = clip.find(".//Name/EffectiveName")
                sample_node = clip.find(".//SampleRef/FileRef/Name")
                search_hint_node = clip.find(".//SampleRef/FileRef/SearchHint")

                clips.append({
                    "clip_name": clip_name_node.attrib.get("Value") if clip_name_node is not None else None,
                    "sample_file": sample_node.attrib.get("Value") if sample_node is not None else None,
                    "sample_path": shorten_path(search_hint_node.attrib.get("Path")) if search_hint_node is not None else ""
                })

            tracks.append({
                "track_name": track_name,
                "track_type": "Audio" if track_tag == "AudioTrack" else "MIDI",
                "clips": clips
            })

    return tracks

def extract_plugin_info(xml_path, project_name):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    ableton_fx = set()
    vst_fx = set()
    au_fx = set()

    for device in root.findall(".//Tracks//DeviceChain//Devices/*"):
        tag = device.tag
        if tag not in ['PluginDevice', 'AuPluginDevice']:
            ableton_fx.add(tag)

    for vst in root.findall(".//PluginDevice//PluginDesc//VstPluginInfo//PlugName"):
        vst_fx.add(vst.attrib.get("Value"))

    for au in root.findall(".//AuPluginDevice//PluginDesc//AuPluginInfo/Name"):
        au_fx.add(au.attrib.get("Value"))

    global_fx = vst_fx.union(au_fx)

    plugin_report = [
        f"Project: {project_name}",
        f"Ableton Effects:",
        ", ".join(sorted(ableton_fx)) or "None",
        "",
        f"Global Plugins (VST/AU):",
        ", ".join(sorted(global_fx)) or "None"
    ]

    txt_path = xml_path.replace(".xml", "_plugins.txt")
    with open(txt_path, "w") as f:
        f.write("\n".join(plugin_report))

    print(f"✅ Plugin list saved to: {txt_path}")

def extract_plugins_by_track(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    plugin_data = []

    for track_tag in ["AudioTrack", "MidiTrack"]:
        for track in root.findall(f".//{track_tag}"):
            name_node = track.find(".//Name/EffectiveName")
            track_name = name_node.attrib.get("Value") if name_node is not None else "Unnamed"

            device_chain = track.find(".//DeviceChain/Devices")
            if device_chain is None:
                continue

            devices = []
            for device in device_chain:
                tag = device.tag

                if tag in ["PluginDevice", "AuPluginDevice"]:
                    plug_name_node = device.find(".//PluginDesc//VstPluginInfo//PlugName") or device.find(".//PluginDesc//AuPluginInfo/Name")
                    if plug_name_node is not None:
                        devices.append(plug_name_node.attrib.get("Value"))
                elif tag not in ["PluginDevice", "AuPluginDevice"]:
                    devices.append(tag)

            if devices:
                plugin_data.append({
                    "track": track_name,
                    "plugins": devices
                })

    return plugin_data

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ableton_extract.py <path_to_als_file>")
        sys.exit(1)

    als_path = sys.argv[1]
    if not os.path.exists(als_path):
        print("File does not exist.")
        sys.exit(1)

    # Step 1: Decompress ALS to XML
    xml_path = decompress_als(als_path)
    print(f"✅ Full XML saved to: {xml_path}")

    # Step 2: Extract track + clip info
    data = extract_track_info(xml_path)

    # Step 3: Print summary
    for track in data:
        print(f"\n🎛️ Track: {track['track_name']} ({track['track_type']})")
        for clip in track["clips"]:
            print(f"   🎹 Clip: {clip['clip_name']}")
            if clip["sample_file"]:
                print(f"       🎧 Sample: {clip['sample_file']}")
            if clip["sample_path"]:
                print(f"       📂 Path: {clip['sample_path']}")

    # Step 4: Export clip summary CSV
    csv_path = xml_path.replace(".xml", "_summary.csv")
    with open(csv_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Track Name", "Track Type", "Clip Name", "Sample File", "Sample Path"])
        for track in data:
            for clip in track["clips"]:
                writer.writerow([
                    track["track_name"],
                    track["track_type"],
                    clip["clip_name"] or "",
                    clip["sample_file"] or "",
                    clip["sample_path"] or ""
                ])
    print(f"\n✅ Summary CSV saved to: {csv_path}")

    # Step 5: Export global/plugin summary
    project_name = os.path.basename(als_path)
    extract_plugin_info(xml_path, project_name)

    # Step 6: Export per-track plugin summary
    grouped_plugins = extract_plugins_by_track(xml_path)
    group_path = xml_path.replace(".xml", "_plugins_by_track.txt")
    with open(group_path, "w") as f:
        for entry in grouped_plugins:
            f.write(f"{entry['track']}:\n")
            for plugin in entry["plugins"]:
                f.write(f"  - {plugin}\n")
            f.write("\n")
    print(f"✅ Plugins-by-track summary saved to: {group_path}")