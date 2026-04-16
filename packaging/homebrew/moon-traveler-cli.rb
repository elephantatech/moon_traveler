class MoonTravelerCli < Formula
  desc "Text-based survival game set on Saturn's moon Enceladus with LLM-powered alien conversations"
  homepage "https://github.com/elephantatech/moon_traveler"
  url "https://github.com/elephantatech/moon_traveler/archive/refs/tags/v0.3.0.tar.gz"
  # sha256 "UPDATE_WITH_ACTUAL_SHA256_AFTER_RELEASE"
  license "Apache-2.0"
  head "https://github.com/elephantatech/moon_traveler.git", branch: "main"

  depends_on "python@3.11"

  def install
    virtualenv_install_with_resources

    # Create model and save directories
    (var/"moon-traveler-cli/models").mkpath
    (var/"moon-traveler-cli/saves").mkpath
  end

  def caveats
    <<~EOS
      Moon Traveler CLI stores models and saves in:
        #{var}/moon-traveler-cli/

      On first launch, the game offers to download an AI model (~1.3 GB).
      The game also works without a model using pre-written dialogue.
    EOS
  end

  test do
    assert_predicate bin/"moon-traveler-cli", :exist?
  end
end
