use std::io::{self, Read, Write};
use std::process;

use ratex_layout::{LayoutOptions, layout, to_display_list};
use ratex_parser::parser::parse;
use ratex_render::{RenderOptions, render_to_png};
use ratex_types::color::Color;
use ratex_types::math_style::MathStyle;

const USAGE: &str = "\
Usage: mp2i-render [OPTIONS]

Renders a LaTeX math formula read from stdin to a PNG written on stdout.

Options:
  --scale <FACTOR>     Device pixel ratio (resolution multiplier) [default: 2.0]
  --color <COLOR>      Formula color [default: white]
  --inline             Use inline math style instead of display style
  -h, --help           Show this help
";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "-h" || a == "--help") {
        print!("{}", USAGE);
        return;
    }

    let flag_value = |flag: &str, default: f32| -> f32 {
        args.iter()
            .position(|a| a == flag)
            .and_then(|i| args.get(i + 1))
            .and_then(|s| s.parse::<f32>().ok())
            .unwrap_or(default)
    };

    let scale = flag_value("--scale", 2.0);
    let color = args
        .iter()
        .position(|a| a == "--color")
        .and_then(|i| args.get(i + 1))
        .and_then(|value| Color::parse(value))
        .unwrap_or(Color::WHITE);
    let style = if args.iter().any(|a| a == "--inline") {
        MathStyle::Text
    } else {
        MathStyle::Display
    };

    let mut formula = String::new();
    if io::stdin().read_to_string(&mut formula).is_err() {
        eprintln!("error: failed to read formula from stdin");
        process::exit(2);
    }
    let formula = formula.trim();
    if formula.is_empty() {
        eprintln!("error: empty formula");
        process::exit(2);
    }

    match render_png(formula, color, scale, style) {
        Ok(png) => {
            io::stdout().write_all(&png).unwrap_or_else(|e| {
                eprintln!("error: failed to write PNG to stdout: {}", e);
                process::exit(2);
            });
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(2);
        }
    }
}

fn render_png(
    formula: &str,
    color: Color,
    scale: f32,
    style: MathStyle,
) -> Result<Vec<u8>, String> {
    let ast = parse(formula).map_err(|e| format!("parse error: {}", e))?;
    let layout_options = LayoutOptions::default().with_style(style).with_color(color);
    let lbox = layout(&ast, &layout_options);
    let display_list = to_display_list(&lbox);

    let render_options = RenderOptions {
        font_size: 40.0,
        padding: 6.0,
        background_color: Color::new(0.0, 0.0, 0.0, 0.0),
        font_dir: String::new(),
        device_pixel_ratio: scale.clamp(0.5, 8.0),
    };

    render_to_png(&display_list, &render_options)
}
