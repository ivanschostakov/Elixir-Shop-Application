Pod::Spec.new do |spec|
  spec.name = 'ElixirChatControls'
  spec.version = '1.0.0'
  spec.summary = 'Native UIKit controls for Elixir Peptide chat'
  spec.homepage = 'https://elixirpeptide.com'
  spec.license = { :type => 'Proprietary' }
  spec.author = 'Elixir Peptide'
  spec.source = { :path => '.' }
  spec.platform = :ios, '15.1'
  spec.swift_version = '5.9'
  spec.static_framework = true
  spec.source_files = '*.swift'
  spec.dependency 'ExpoModulesCore'
end
