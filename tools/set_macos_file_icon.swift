// Set Finder's custom file icon through AppKit; no Finder scripting permission.
import AppKit
import Foundation

guard CommandLine.arguments.count == 3,
      let icon = NSImage(contentsOfFile: CommandLine.arguments[1]),
      NSWorkspace.shared.setIcon(icon, forFile: CommandLine.arguments[2], options: []) else {
    fputs("Could not apply the application icon to the DMG file.\n", stderr)
    exit(1)
}
