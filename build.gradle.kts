import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.targets.js.nodejs.NodeJsEnvSpec
import org.jetbrains.kotlin.gradle.targets.js.nodejs.NodeJsPlugin
import org.jetbrains.kotlin.gradle.targets.js.npm.NpmExtension
import java.time.Duration

plugins {
    kotlin("multiplatform") version "2.4.21"
    id("org.jlleitschuh.gradle.ktlint") version "14.2.0"
    id("dev.detekt") version "2.0.0-alpha.6"
    `maven-publish`
    signing
}

kotlin {
    explicitApi()

    compilerOptions {
        allWarningsAsErrors.set(true)
    }

    jvm {
        compilerOptions.jvmTarget.set(JvmTarget.JVM_17)
        // The library has no Java sources. Align the published JVM compatibility.
        tasks.withType<JavaCompile>().configureEach {
            options.release.set(17)
            targetCompatibility = "17"
        }
        testRuns["test"].executionTask.configure {
            timeout.set(Duration.ofMinutes(5))
        }
    }

    js {
        nodejs()
    }

    sourceSets.commonTest.dependencies {
        implementation(kotlin("test"))
    }
}

plugins.withType<NodeJsPlugin> {
    extensions.getByType<NodeJsEnvSpec>().download = false
}

extensions.configure<NpmExtension> {
    // Kotlin's test runner still requests older versions of these transitive tools.
    override("diff", "8.0.3")
    override("glob", "14.0.6")
    override("minimatch", "11.0.9")
    override("serialize-javascript", "7.1.4")
}

configurations.configureEach {
    resolutionStrategy.eachDependency {
        when (requested.group) {
            "ch.qos.logback" -> useVersion("1.6.8")
            "org.bouncycastle" -> if (requested.name.endsWith("-jdk18on")) useVersion("1.87")
        }
    }
}

dependencyLocking {
    lockAllConfigurations()
    lockMode.set(LockMode.STRICT)
}

ktlint {
    version.set("1.8.0")
}

detekt {
    buildUponDefaultConfig = true
    source.setFrom(files("src", "examples"))
}

publishing {
    publications.withType<MavenPublication>().configureEach {
        val publicationName = name
        val documentationJar =
            tasks.register<Jar>("${publicationName}JavadocJar") {
                archiveAppendix.set(publicationName)
                archiveClassifier.set("javadoc")
                from("README.md")
            }
        artifact(documentationJar)
        pom {
            name.set("Kotlin pipeline example")
            description.set("Kotlin Multiplatform example for the AI-driven development pipeline template")
            url.set("https://github.com/link-foundation/kotlin-ai-driven-development-pipeline-template")
            licenses {
                license {
                    name.set("The Unlicense")
                    url.set("https://unlicense.org/")
                }
            }
            developers {
                developer {
                    id.set("link-foundation")
                    name.set("Link Foundation")
                }
            }
            scm {
                url.set("https://github.com/link-foundation/kotlin-ai-driven-development-pipeline-template")
                connection.set("scm:git:https://github.com/link-foundation/kotlin-ai-driven-development-pipeline-template.git")
            }
        }
    }
    repositories {
        maven {
            name = "Bundle"
            url =
                layout.buildDirectory
                    .dir("maven-bundle")
                    .get()
                    .asFile
                    .toURI()
        }
    }
}

val signPublications = providers.environmentVariable("SIGNING_KEY")
if (signPublications.isPresent) {
    signing {
        useInMemoryPgpKeys(signPublications.get(), providers.environmentVariable("SIGNING_PASSWORD").getOrElse(""))
        sign(publishing.publications)
    }
}

val jvmJar = tasks.named<Jar>("jvmJar")

tasks.register<Sync>("stageRuntime") {
    from(jvmJar)
    from(configurations.named("jvmRuntimeClasspath"))
    into(layout.buildDirectory.dir("runtime"))
}
