import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Services.SystemTray
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.ishesatoshi.phonon"
  ipcTarget: "io.github.ishesatoshi.phonon"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  readonly property string pluginDir: decodeURIComponent(String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "")).replace(/\/$/, "")
  readonly property var trayItem: {
    var items = SystemTray.items.values
    for (var i = 0; i < items.length; i++)
      if (String(items[i].id) === "phonon") return items[i]
    return null
  }
  readonly property string description: trayItem ? String(trayItem.tooltipDescription || "").toLowerCase() : ""
  readonly property string phase: !trayItem ? "stopped"
    : description.indexOf("recording") === 0 ? "recording"
    : description.indexOf("transcribing") === 0 ? "transcribing"
    : description.indexOf("ready") === 0 ? "ready" : "starting"
  readonly property bool recording: phase === "recording"
  readonly property string iconSource: Quickshell.iconPath("phonon", true)
  property var info: ({ mode: "minimal", mic_name: "", mic_muted: false,
    mic_volume: 0, history_enabled: false, last_text: "", last_duration: 0 })
  property bool actionFailed: false
  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  // The tray already supplies live state. Read optional details only while open.
  Timer {
    interval: 1500
    running: root.opened
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!refresh.running) refresh.running = true
  }
  Process {
    id: refresh
    command: ["python3", root.pluginDir + "/status.py", "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var value = JSON.parse(this.text)
          if (!value.error) root.info = value
        } catch (error) { root.actionFailed = true }
      }
    }
  }
  Process {
    id: actions
    function perform(args) {
      if (running) return
      root.actionFailed = false
      command = ["python3", root.pluginDir + "/status.py"].concat(args)
      running = true
    }
    onExited: function(code) {
      root.actionFailed = code !== 0
      if (root.opened && !refresh.running) refresh.running = true
    }
  }
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    active: root.recording || root.opened
    tooltipText: strings.t("tooltip")
    iconComponent: Component {
      Item {
        implicitWidth: Style.bar.iconCanvas
        implicitHeight: Style.bar.iconCanvas
        Image {
          id: logo
          anchors.fill: parent
          source: root.iconSource
          fillMode: Image.PreserveAspectFit
          visible: status === Image.Ready
        }
        Text {
          anchors.centerIn: parent
          visible: !logo.visible
          text: "φ"
          textFormat: Text.PlainText
          color: Commons.Color.foreground
          font.pixelSize: Style.bar.iconCanvas
        }
      }
    }
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.RightButton && root.trayItem && root.phase !== "transcribing")
        actions.perform(["toggle"])
      else if (mouseButton !== Qt.RightButton) root.toggle()
    }
  }
  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: popup.fittedContentWidth(Style.space(350))
    contentHeight: popup.fittedContentHeight(popup.loadedContentHeight, Style.space(550))
    content: PanelKeyCatcher {
      anchors.fill: parent
      implicitHeight: layout.implicitHeight + Style.space(24)
      onCloseRequested: root.close()
      Flickable {
        anchors.fill: parent
        contentHeight: layout.implicitHeight + Style.space(24)
        clip: true
        ColumnLayout {
          id: layout
          x: Style.space(12)
          y: Style.space(12)
          width: parent.width - Style.space(24)
          spacing: Style.space(10)
          Text {
            text: "Phonon"
            textFormat: Text.PlainText
            font.family: Style.font.family
            font.pixelSize: Style.font.title
            font.bold: true
            color: Commons.Color.foreground
          }
          Text {
            text: strings.t("state." + root.phase)
            textFormat: Text.PlainText
            color: root.recording ? Commons.Color.urgent : Commons.Color.accent
            font.family: Style.font.family
            font.pixelSize: Style.font.body
          }
          Button {
            Layout.fillWidth: true
            text: strings.t(root.recording ? "stop" : "start")
            enabled: !!root.trayItem && root.phase !== "starting" && root.phase !== "transcribing" && !actions.running
            bordered: true
            onClicked: {
              // Restore the previous text field before recording or pasting.
              root.close()
              actions.perform(["toggle"])
            }
          }
          PanelSeparator { Layout.fillWidth: true }
          PanelSectionHeader { text: strings.t("mode") }
          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(4)
            Repeater {
              model: ["minimal", "casual", "formal", "prompt"]
              Button {
                required property string modelData
                Layout.fillWidth: true
                text: strings.t("mode." + modelData)
                selected: root.info.mode === modelData
                enabled: !!root.trayItem && !actions.running
                bordered: true
                onClicked: actions.perform(["set_mode", modelData])
              }
            }
          }
          PanelSeparator { Layout.fillWidth: true }
          PanelSectionHeader { text: strings.t("microphone") }
          Text {
            Layout.fillWidth: true
            text: root.info.mic_name
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            color: Commons.Color.foreground
          }
          Button {
            visible: root.info.mic_muted
            text: strings.t("unmute")
            bordered: true
            onClicked: actions.perform(["unmute"])
          }
          PanelSeparator { Layout.fillWidth: true }
          PanelSectionHeader { text: strings.t("last") }
          Text {
            Layout.fillWidth: true
            text: !root.info.history_enabled ? strings.t("historyOff")
              : root.info.last_text || strings.t("historyEmpty")
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            color: Commons.Color.foreground
          }
          Button {
            visible: root.info.history_enabled && root.info.last_text !== ""
            text: strings.t("copy")
            bordered: true
            onClicked: actions.perform(["copy_last"])
          }
          Text {
            Layout.fillWidth: true
            text: strings.t("shortcuts")
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            color: Commons.Color.muted
          }
          Text {
            visible: root.actionFailed
            Layout.fillWidth: true
            text: strings.t("error")
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: Commons.Color.urgent
          }
          Button {
            Layout.fillWidth: true
            text: strings.t("folder")
            bordered: true
            onClicked: actions.perform(["open_dir"])
          }
        }
      }
    }
  }
}
