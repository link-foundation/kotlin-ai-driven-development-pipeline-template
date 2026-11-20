package template

/** Returns a greeting for the supplied [name], using a default for blank input. */
public fun greeting(name: String = "Kotlin"): String = "Hello, ${name.trim().ifEmpty { "Kotlin" }}!"
