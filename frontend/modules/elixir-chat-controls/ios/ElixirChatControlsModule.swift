import ExpoModulesCore
import UIKit

public final class ElixirChatControlsModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ElixirChatControls")
    Constant("interfaceVersion") { 8 }


    View(ChatActionControl.self) {
      ViewName("ActionControl")
      Events("onAction")
      Prop("action") { (view, action: String) in view.action = ChatAction(rawValue: action) ?? .send }
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

    View(ChatTitleMaterial.self) {
      ViewName("TitleMaterial")
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
    }

    View(ChatInputMaterial.self) {
      ViewName("InputMaterial")
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
      Prop("joined", false) { (view, joined: Bool) in view.joined = joined }
    }
    View(ChatMenuControl.self) {
      ViewName("MenuControl")
      Events("onSelect")
      Prop("label") { (view, label: String) in view.label = label }
      Prop("labels") { (view, labels: [String]) in view.labels = labels }
      Prop("details") { (view, details: [String]) in view.details = details }
      Prop("selectedIndex") { (view, index: Int) in view.selectedIndex = index }
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
      OnViewDidUpdateProps { view in view.updateControl() }
    }
  }
}

private final class ChatMenuControl: ExpoView {
  let onSelect = EventDispatcher()
  var label = ""
  var labels: [String] = []
  var details: [String] = []
  var selectedIndex = -1
  private let button = UIButton(type: .system)

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    addSubview(button)
    button.showsMenuAsPrimaryAction = true
  }

  override func layoutSubviews() { super.layoutSubviews(); button.frame = bounds }

  func updateControl() {
    var config: UIButton.Configuration
    if #available(iOS 26.0, *) { config = .glass() }
    else { config = .tinted() }
    config.cornerStyle = .capsule
    config.title = label
    config.image = UIImage(systemName: "clock.arrow.circlepath")
    config.imagePadding = 8
    config.baseForegroundColor = .label
    button.configuration = config
    button.accessibilityLabel = label
    button.menu = UIMenu(children: labels.enumerated().map { index, title in
      let action = UIAction(title: title, state: index == selectedIndex ? .on : .off) { [weak self] _ in self?.onSelect(["index": index]) }
      if #available(iOS 16.0, *), details.indices.contains(index) { action.subtitle = details[index] }
      return action
    })
  }
}





private final class ChatInputMaterial: ExpoView {
  private let material = UIVisualEffectView()
  private var lastSize = CGSize.zero
  private var animator: UIViewPropertyAnimator?
  var joined = false {
    didSet {
      guard joined != oldValue else { return }
      updateFrame(animated: window != nil)
    }
  }

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    isUserInteractionEnabled = false
    if #available(iOS 26.0, *) {
      let glass = UIGlassEffect(style: .regular)
      glass.tintColor = chatControlFill.withAlphaComponent(0.55)
      material.effect = glass
    } else {
      material.effect = UIBlurEffect(style: .systemThinMaterial)
    }
    material.layer.cornerRadius = 22
    material.layer.borderWidth = 0.5
    material.layer.borderColor = UIColor.white.withAlphaComponent(0.6).cgColor
    material.clipsToBounds = true
    addSubview(material)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    guard bounds.size != lastSize else { return }
    lastSize = bounds.size
    updateFrame(animated: false)
  }

  private func updateFrame(animated: Bool) {
    if animator?.state == .active {
      animator?.stopAnimation(false)
      animator?.finishAnimation(at: .current)
    }
    animator = nil
    let frame = CGRect(x: 0, y: 0, width: max(0, bounds.width - (joined ? 0 : 50)), height: bounds.height)
    guard animated && !UIAccessibility.isReduceMotionEnabled else {
      material.frame = frame
      return
    }
    let next = UIViewPropertyAnimator(duration: 0.32, dampingRatio: 0.88) { self.material.frame = frame }
    animator = next
    next.startAnimation()
  }
}


private final class ChatActionControl: ExpoView {
  let onAction = EventDispatcher()
  let button = ChatActionButton(type: .system)
  var action: ChatAction = .send

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

private final class ChatTitleMaterial: ExpoView {
  private let material = UIVisualEffectView()

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    isUserInteractionEnabled = false
    if #available(iOS 26.0, *) {
      material.effect = UIGlassEffect(style: .regular)
    } else {
      material.effect = UIBlurEffect(style: .systemThinMaterial)
    }
    material.clipsToBounds = true
    addSubview(material)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    material.frame = bounds
    material.layer.cornerRadius = bounds.height / 2
  }
}
