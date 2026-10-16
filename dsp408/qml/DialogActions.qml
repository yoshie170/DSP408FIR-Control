import QtQuick
import QtQuick.Layouts
Item {
    default property alias actions: row.data
    property alias spacing: row.spacing
    implicitWidth: row.implicitWidth+36
    implicitHeight: row.implicitHeight+24
    RowLayout { id: row; anchors.fill: parent; anchors.leftMargin: 18; anchors.rightMargin: 18; anchors.topMargin: 12; anchors.bottomMargin: 12; spacing: 8 }
}
