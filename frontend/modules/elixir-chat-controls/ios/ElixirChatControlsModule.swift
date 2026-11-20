import ExpoModulesCore
import UIKit

public final class ElixirChatControlsModule: Module {
  public func definition() -> ModuleDefinition {
    Name("ElixirChatControls")
    Constant("interfaceVersion") { 6 }

    View(ChatModeControl.self) {
      ViewName("ModeControl")
      Events("onSelect")
      Prop("labels") { (view, labels: [String]) in view.labels = labels }
      Prop("badges") { (view, badges: [String]) in view.badges = badges }
      Prop("selectedIndex") { (view, index: Int) in view.selectedIndex = index }
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
      OnViewDidUpdateProps { view in view.updateControl() }
    }

    View(ChatActionControl.self) {
      ViewName("ActionControl")
      Events("onAction")
      Prop("action") { (view, action: String) in view.action = ChatAction(rawValue: action) ?? .microphone }
      Prop("title", "") { (view, title: String) in view.title = title }
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

    View(ChatInputMaterial.self) {
      ViewName("InputMaterial")
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
      Prop("joined", false) { (view, joined: Bool) in view.joined = joined }
    }
    View(ChatTitleMaterial.self) {
      ViewName("TitleMaterial")
      Prop("dark") { (view, dark: Bool) in view.overrideUserInterfaceStyle = dark ? .dark : .light }
    }
    View(ChatKeyboardMaterial.self) {
      ViewName("KeyboardMaterial")
      Prop("dark") { (view, dark: Bool) in view.material.setDark(dark) }
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

private final class ChatModeControl: ExpoView {
  let onSelect = EventDispatcher()
  var labels: [String] = []
  var badges: [String] = []
  var selectedIndex = 0
  private let material = UIVisualEffectView()
  private let selection = UIVisualEffectView()
  private var buttons: [UIButton] = []
  private var captions: [ChatTabCaption] = []
  private var animator: UIViewPropertyAnimator?
  private var displayedSelection = -1
  private var laidOutSize = CGSize.zero

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    accessibilityTraits = .tabBar
    if #available(iOS 26.0, *) {
      material.effect = UIGlassEffect(style: .regular)
      let glass = UIGlassEffect(style: .regular)
      glass.tintColor = UIColor.systemGray3.withAlphaComponent(0.35)
      glass.isInteractive = true
      selection.effect = glass
    } else {
      material.effect = UIBlurEffect(style: .systemThinMaterial)
      selection.backgroundColor = .systemGray5
    }
    material.isUserInteractionEnabled = false
    selection.isUserInteractionEnabled = false
    material.clipsToBounds = true
    selection.clipsToBounds = true
    addSubview(material)
    addSubview(selection)
    let pan = UIPanGestureRecognizer(target: self, action: #selector(dragSelection(_:)))
    addGestureRecognizer(pan)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    material.frame = bounds
    material.layer.cornerRadius = bounds.height / 2
    selection.layer.cornerRadius = max(0, bounds.height - 8) / 2
    let width = itemWidth
    for (index, button) in buttons.enumerated() {
      button.frame = CGRect(x: 4 + CGFloat(index) * width, y: 0, width: width, height: bounds.height)
      captions[index].frame = button.bounds
    }
    guard laidOutSize != bounds.size else { return }
    laidOutSize = bounds.size
    moveSelection(animated: false)
  }

  private var itemWidth: CGFloat { max(0, bounds.width - 8) / CGFloat(max(1, buttons.count)) }

  func updateControl() {
    if buttons.count != labels.count {
      buttons.forEach { $0.removeFromSuperview() }
      captions = labels.map { _ in ChatTabCaption(frame: .zero) }
      buttons = captions.enumerated().map { index, caption in
        let button = UIButton(type: .system)
        button.tag = index
        button.addSubview(caption)
        button.addTarget(self, action: #selector(selectTab(_:)), for: .touchUpInside)
        addSubview(button)
        return button
      }
      laidOutSize = .zero
      setNeedsLayout()
    }
    for (index, caption) in captions.enumerated() {
      let badge = badges.indices.contains(index) ? badges[index] : ""
      caption.update(title: labels[index], badge: badge, selected: index == selectedIndex)
      buttons[index].accessibilityLabel = badge.isEmpty ? labels[index] : "\(labels[index]), \(badge)"
      buttons[index].accessibilityTraits = index == selectedIndex ? [.button, .selected] : .button
    }
    guard displayedSelection != selectedIndex else { return }
    moveSelection(animated: window != nil)
  }

  private func stopAnimation() {
    if animator?.state == .active {
      animator?.stopAnimation(false)
      animator?.finishAnimation(at: .current)
    }
    animator = nil
  }

  private func moveSelection(animated: Bool) {
    stopAnimation()
    displayedSelection = selectedIndex
    selection.isHidden = !buttons.indices.contains(selectedIndex)
    let frame = CGRect(x: 4 + CGFloat(selectedIndex) * itemWidth, y: 4, width: itemWidth, height: max(0, bounds.height - 8))
    guard animated && !UIAccessibility.isReduceMotionEnabled else { selection.frame = frame; return }
    let next = UIViewPropertyAnimator(duration: 0.28, dampingRatio: 0.88) { [weak self] in self?.selection.frame = frame }
    animator = next
    next.startAnimation()
  }

  private func commitSelection(_ index: Int) {
    guard buttons.indices.contains(index) else { return }
    let changed = selectedIndex != index
    selectedIndex = index
    for (position, caption) in captions.enumerated() {
      caption.setSelected(position == index)
      buttons[position].accessibilityTraits = position == index ? [.button, .selected] : .button
    }
    moveSelection(animated: true)
    if changed { onSelect(["index": index]) }
  }

  @objc private func selectTab(_ button: UIButton) { commitSelection(button.tag) }

  @objc private func dragSelection(_ gesture: UIPanGestureRecognizer) {
    guard itemWidth > 0, !buttons.isEmpty else { return }
    let x = gesture.location(in: self).x
    let index = min(buttons.count - 1, max(0, Int((x - 4) / itemWidth)))
    switch gesture.state {
    case .began, .changed:
      stopAnimation()
      selection.frame.origin.x = min(bounds.width - 4 - itemWidth, max(4, x - itemWidth / 2))
    case .ended:
      commitSelection(index)
    case .cancelled, .failed:
      moveSelection(animated: true)
    default: break
    }
  }
}

private final class ChatTabCaption: UIView {
  private let title = UILabel()
  private let badge = ChatUnreadBadge()

  override init(frame: CGRect) {
    super.init(frame: frame)
    isUserInteractionEnabled = false
    title.textColor = .label
    title.adjustsFontSizeToFitWidth = true
    title.minimumScaleFactor = 0.8
    title.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
    badge.font = .systemFont(ofSize: 12, weight: .semibold)
    badge.textColor = .white
    badge.backgroundColor = .systemGray2
    badge.textAlignment = .center
    badge.layer.cornerRadius = 10
    badge.clipsToBounds = true
    badge.setContentCompressionResistancePriority(.defaultHigh, for: .horizontal)
    let row = UIStackView(arrangedSubviews: [title, badge])
    row.axis = .horizontal
    row.alignment = .center
    row.spacing = 4
    row.translatesAutoresizingMaskIntoConstraints = false
    addSubview(row)
    let minimumBadgeWidth = badge.widthAnchor.constraint(greaterThanOrEqualToConstant: 20)
    minimumBadgeWidth.priority = .defaultHigh
    NSLayoutConstraint.activate([
      row.centerXAnchor.constraint(equalTo: centerXAnchor),
      row.centerYAnchor.constraint(equalTo: centerYAnchor),
      row.leadingAnchor.constraint(greaterThanOrEqualTo: leadingAnchor, constant: 4),
      row.trailingAnchor.constraint(lessThanOrEqualTo: trailingAnchor, constant: -4),
      badge.heightAnchor.constraint(equalToConstant: 20),
      minimumBadgeWidth,
    ])
  }

  @available(*, unavailable)
  required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }

  func update(title: String, badge: String, selected: Bool) {
    self.title.text = title
    self.badge.text = badge
    self.badge.isHidden = badge.isEmpty
    setSelected(selected)
  }

  func setSelected(_ selected: Bool) {
    title.font = .systemFont(ofSize: 14, weight: selected ? .bold : .semibold)
  }
}

private final class ChatUnreadBadge: UILabel {
  override var intrinsicContentSize: CGSize {
    let size = super.intrinsicContentSize
    return CGSize(width: max(20, size.width + 10), height: 20)
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
    material.layer.cornerRadius = 22
    material.clipsToBounds = true
    addSubview(material)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    material.frame = bounds
    material.layer.cornerRadius = bounds.height / 2
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

private final class ChatKeyboardMaterial: ExpoView {
  let material = ChatMaterialView(frame: .zero)
  private var observers: [NSObjectProtocol] = []
  private var keyboardFrame = CGRect.null

  required init(appContext: AppContext? = nil) {
    super.init(appContext: appContext)
    isUserInteractionEnabled = false
    clipsToBounds = true
    material.isHidden = true
    addSubview(material)
    for name in [UIResponder.keyboardWillChangeFrameNotification, UIResponder.keyboardWillHideNotification] {
      observers.append(NotificationCenter.default.addObserver(forName: name, object: nil, queue: .main) { [weak self] notification in
        guard let self else { return }
        let info = notification.userInfo ?? [:]
        self.keyboardFrame = name == UIResponder.keyboardWillHideNotification ? .null : (info[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect ?? .null)
        let duration = info[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double ?? 0.25
        let curve = info[UIResponder.keyboardAnimationCurveUserInfoKey] as? UInt ?? 7
        UIView.animate(withDuration: duration, delay: 0, options: [UIView.AnimationOptions(rawValue: curve << 16), .beginFromCurrentState, .allowUserInteraction]) {
          self.updateFrame()
        }
      })
    }
  }

  deinit { observers.forEach(NotificationCenter.default.removeObserver) }

  override func layoutSubviews() {
    super.layoutSubviews()
    updateFrame()
  }

  private func updateFrame() {
    guard let window, !keyboardFrame.isNull else { material.isHidden = true; return }
    let frame = convert(keyboardFrame, from: window.screen.coordinateSpace)
    let height = max(0, bounds.maxY - frame.minY)
    material.isHidden = height <= 0
    material.frame = CGRect(x: 0, y: frame.minY - 32, width: bounds.width, height: height + 32)
  }
}

private final class ChatActionControl: ExpoView {
  let onAction = EventDispatcher()
  let button = ChatActionButton(type: .system)
  var action: ChatAction = .microphone
  var title = ""

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
    button.setChatAction(action, title: title)
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
