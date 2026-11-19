import UIKit

enum ChatAction: String {
  case back, attachment, latest, microphone, send, stop, busy

  var symbol: String? {
    switch self {
    case .back: return "chevron.left"
    case .attachment: return "paperclip"
    case .latest: return "chevron.down"
    case .microphone: return "mic"
    case .send: return "paperplane.fill"
    case .stop: return "stop.fill"
    case .busy: return nil
    }
  }
}

final class ChatActionButton: UIButton {
  private var displayedAction: ChatAction?

  func setChatAction(_ action: ChatAction) {
    guard displayedAction != action else { return }

    var next: UIButton.Configuration
    if #available(iOS 26.0, *) {
      next = action == .send ? .prominentGlass() : .glass()
    } else {
      next = action == .send ? .filled() : .tinted()
      next.baseBackgroundColor = action == .send ? .systemBlue : .secondarySystemFill
    }
    tintColor = .systemBlue
    next.cornerStyle = .capsule
    next.contentInsets = .zero
    next.baseForegroundColor = action == .send ? .white : (action == .stop ? .systemRed : .label)
    next.preferredSymbolConfigurationForImage = .init(pointSize: 18, weight: .semibold)
    if let symbol = action.symbol, let image = UIImage(systemName: symbol) {
      next.image = action == .send ? image.withTintColor(.white, renderingMode: .alwaysOriginal) : image
    }
    next.showsActivityIndicator = action == .busy

    layer.cornerRadius = min(bounds.width, bounds.height) / 2
    let fill = action == .send ? UIColor.systemBlue : chatControlFill
    if displayedAction != nil && window != nil && !UIAccessibility.isReduceMotionEnabled {
      UIView.transition(with: self, duration: 0.22, options: [.transitionCrossDissolve, .allowUserInteraction, .beginFromCurrentState]) {
        self.configuration = next
        self.backgroundColor = fill
      }
    } else {
      configuration = next
      backgroundColor = fill
    }
    displayedAction = action
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    layer.cornerRadius = min(bounds.width, bounds.height) / 2
  }
}

let chatControlFill = UIColor { traits in
  traits.userInterfaceStyle == .dark
    ? UIColor(red: 0.15, green: 0.19, blue: 0.25, alpha: 1)
    : UIColor(red: 0.95, green: 0.98, blue: 0.96, alpha: 1)
}

final class ChatMaterialView: UIView {
  private let material = UIVisualEffectView()
  private let fade = ComposerFadeMask(frame: .zero)
  private var laidOutSize = CGSize.zero
  private var blurAnimator: UIViewPropertyAnimator?
  private var dark = false
  var topEdge = false {
    didSet {
      guard topEdge != oldValue else { return }
      laidOutSize = .zero
      setNeedsLayout()
    }
  }

  override init(frame: CGRect) {
    super.init(frame: frame)
    isUserInteractionEnabled = false
    addSubview(material)
  }

  @available(*, unavailable)
  required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }

  deinit {
    blurAnimator?.stopAnimation(true)
  }

  override func didMoveToWindow() {
    super.didMoveToWindow()
    updateBlur()
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    material.frame = bounds
    guard laidOutSize != bounds.size else { return }
    laidOutSize = bounds.size
    fade.frame = bounds
    let height = max(bounds.height, 1)
    let middle = min(13 / height, 0.65)
    let end = min(32 / height, 1)
    fade.gradient.startPoint = CGPoint(x: 0.5, y: topEdge ? 1 : 0)
    fade.gradient.endPoint = CGPoint(x: 0.5, y: topEdge ? 0 : 1)
    fade.gradient.locations = [0, NSNumber(value: middle), NSNumber(value: end)]
    material.mask = fade
  }

  func setDark(_ dark: Bool) {
    guard self.dark != dark else { return }
    self.dark = dark
    overrideUserInterfaceStyle = dark ? .dark : .light
    updateBlur()
  }

  private func updateBlur() {
    blurAnimator?.stopAnimation(true)
    blurAnimator = nil
    material.effect = nil
    guard window != nil else { return }

    let blur = UIBlurEffect(style: dark ? .systemUltraThinMaterialDark : .systemUltraThinMaterialLight)
    // Set the material's strength without fading the view that samples the chat behind it.
    let animator = UIViewPropertyAnimator(duration: 1, curve: .linear) { [weak material] in
      material?.effect = blur
    }
    animator.fractionComplete = 0.40
    blurAnimator = animator
  }
}

private final class ComposerFadeMask: UIView {
  override class var layerClass: AnyClass { CAGradientLayer.self }
  var gradient: CAGradientLayer { layer as! CAGradientLayer }

  override init(frame: CGRect) {
    super.init(frame: frame)
    gradient.colors = [UIColor.clear.cgColor, UIColor.black.withAlphaComponent(0.38).cgColor, UIColor.black.cgColor]
  }

  @available(*, unavailable)
  required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
}
