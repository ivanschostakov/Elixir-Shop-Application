import ExpoModulesCore
import UIKit

public final class ElixirChatControlsModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ElixirChatControls")

    View(ChatModeControl.self) {
      ViewName("ModeControl")
      Events("onSelect")
      Prop("labels") { (view, labels: [String]) in view.labels = labels }
      Prop("selectedIndex") { (view, index: Int) in view.selectedIndex = index }
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
      OnViewDidUpdateProps { view in view.updateControl() }
    }

    View(ChatActionControl.self) {
      ViewName("ActionControl")
      Events("onAction")
      Prop("action") { (view, action: String) in view.action = ChatAction(rawValue: action) ?? .microphone }
      Prop("label") { (view, label: String) in view.button.accessibilityLabel = label }
      Prop("disabled", false) { (view, disabled: Bool) in view.button.isEnabled = !disabled }
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
      OnViewDidUpdateProps { view in view.updateControl() }
    }

    View(ChatComposerMaterial.self) {
      ViewName("ComposerMaterial")
      Prop("dark") { (view, dark: Bool) in view.material.setDark(dark) }
      Prop("topEdge", false) { (view, topEdge: Bool) in view.material.topEdge = topEdge }
    }
  }
}

private final class ChatModeControl: ExpoView {
  let onSelect = EventDispatcher()
  var labels: [String] = []
  var selectedIndex = 0
  private let backing = UIView()
  private let control = UISegmentedControl()

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    backing.backgroundColor = chatControlFill
    backing.isUserInteractionEnabled = false
    addSubview(backing)
    addSubview(control)
    control.apportionsSegmentWidthsByContent = true
    control.addTarget(self, action: #selector(selectMode), for: .valueChanged)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    backing.frame = bounds
    backing.layer.cornerRadius = min(bounds.width, bounds.height) / 2
    control.frame = bounds
  }

  func updateControl() {
    if control.numberOfSegments != labels.count {
      control.removeAllSegments()
      for (index, label) in labels.enumerated() {
        control.insertSegment(withTitle: label, at: index, animated: false)
      }
    } else {
      for (index, label) in labels.enumerated() where control.titleForSegment(at: index) != label {
        control.setTitle(label, forSegmentAt: index)
      }
    }
    if control.selectedSegmentIndex != selectedIndex {
      control.selectedSegmentIndex = selectedIndex
    }
  }

  @objc private func selectMode() {
    onSelect(["index": control.selectedSegmentIndex])
  }
}

private final class ChatActionControl: ExpoView {
  let onAction = EventDispatcher()
  let button = ChatActionButton(type: .system)
  var action: ChatAction = .microphone

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    addSubview(button)
    button.addTarget(self, action: #selector(press), for: .touchUpInside)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    button.frame = bounds
  }

  func updateControl() {
    button.setChatAction(action)
  }

  @objc private func press() {
    onAction()
  }
}

private final class ChatComposerMaterial: ExpoView {
  let material = ChatMaterialView(frame: .zero)

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    addSubview(material)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    material.frame = bounds
  }
}
